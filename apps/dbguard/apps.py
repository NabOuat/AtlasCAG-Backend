import logging
import os
import sys

from django.apps import AppConfig

logger = logging.getLogger('dbguard')

DBGUARD_STARTUP_LOCK_KEY = 875_219_002  # distinct de celle de verify_schema.py (875_219_001)

# Commandes pendant lesquelles la vérification automatique ne doit PAS se déclencher
# (migrate/makemigrations la rendraient redondante ou risqueraient une récursion ;
# les autres sont des commandes d'introspection/maintenance qui ne doivent pas être
# perturbées par une écriture de schéma en arrière-plan).
_SKIP_COMMANDS = {
    'migrate', 'makemigrations', 'verify_schema', 'test', 'shell', 'shell_plus',
    'dbshell', 'collectstatic', 'createsuperuser', 'showmigrations', 'sqlmigrate',
}


class DbguardConfig(AppConfig):
    name = "apps.dbguard"
    verbose_name = "Vérification du schéma de base de données"

    def ready(self):
        argv = sys.argv
        command = argv[1] if len(argv) > 1 else None
        if command in _SKIP_COMMANDS:
            return

        # Sous `runserver`, Django relance le process une fois pour l'auto-reload ;
        # RUN_MAIN n'est présent QUE dans le sous-process qui sert réellement les requêtes.
        # Hors runserver (gunicorn, etc.), RUN_MAIN n'est jamais défini — la vérification
        # s'exécute alors normalement au premier (et unique) démarrage du process.
        if 'runserver' in argv and os.environ.get('RUN_MAIN') != 'true':
            return

        from django.core.management import call_command
        from django.db import connection

        # Verrou Postgres pour sérialiser cette séquence migrate+verify_schema entre plusieurs
        # process/workers démarrant en même temps — sans lui, deux `migrate` concurrents peuvent
        # se marcher dessus (l'un des symptômes observés : une table déjà créée par un process
        # se voit retenter une CREATE TABLE par un autre, qui échoue en DuplicateTable).
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [DBGUARD_STARTUP_LOCK_KEY])
            got_lock = cursor.fetchone()[0]
        if not got_lock:
            logger.info("Un autre process exécute déjà migrate+verify_schema au démarrage — ignoré ici.")
            return

        try:
            try:
                call_command('migrate', interactive=False, verbosity=0)
            except Exception:
                logger.exception(
                    "L'application automatique des migrations au démarrage a échoué — "
                    "l'application démarre quand même, mais lancez "
                    "`python manage.py migrate` manuellement pour investiguer."
                )
                return  # inutile de vérifier le schéma si migrate lui-même a échoué

            try:
                call_command('verify_schema', fix=True)
            except Exception:
                logger.exception(
                    "La vérification automatique du schéma a échoué au démarrage — "
                    "l'application démarre quand même, mais lancez "
                    "`python manage.py verify_schema` manuellement pour investiguer."
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [DBGUARD_STARTUP_LOCK_KEY])
