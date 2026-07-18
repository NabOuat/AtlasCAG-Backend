from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Réinitialise le mot de passe et/ou réactive un utilisateur AtlasCAG'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', default=None, help='Nom d\'utilisateur à réinitialiser')
        parser.add_argument('--password', '-p', help='Nouveau mot de passe (interactif si absent)')
        parser.add_argument('--activate', '-a', action='store_true', help='Réactive le compte si désactivé')
        parser.add_argument('--superuser', '-s', action='store_true', help='Donne les droits superuser')
        parser.add_argument('--list', '-l', action='store_true', help='Liste tous les utilisateurs')

    def handle(self, *args, **options):
        if options['list'] or not options['username']:
            self._list_users()
            return

        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'Utilisateur "{username}" introuvable.')

        changed = False

        # Réactivation
        if options['activate'] and not user.is_active:
            user.is_active = True
            changed = True
            self.stdout.write(f'  Compte réactivé')

        # Droits superuser
        if options['superuser']:
            user.is_staff = True
            user.is_superuser = True
            changed = True
            self.stdout.write(f'  Droits superuser accordés')

        # Mot de passe
        pwd = options['password']
        if not pwd:
            import getpass
            pwd = getpass.getpass(f'Nouveau mot de passe pour "{username}" : ')
            confirm = getpass.getpass('Confirmer : ')
            if pwd != confirm:
                raise CommandError('Les mots de passe ne correspondent pas.')

        user.set_password(pwd)
        changed = True

        # Invalider les tokens JWT (blacklist)
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            tokens = OutstandingToken.objects.filter(user=user)
            count = tokens.count()
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
            if count:
                self.stdout.write(f'  {count} token(s) JWT invalidé(s)')
        except Exception:
            pass  # module blacklist absent ou tokens déjà expirés

        if changed:
            user.save()

        self.stdout.write(self.style.SUCCESS(
            f'\nUtilisateur "{username}" ({user.profil}) réinitialisé avec succès.'
        ))

    def _list_users(self):
        users = User.objects.all().order_by('profil', 'username')
        self.stdout.write(f'\n{"Username":<20} {"Profil":<16} {"Actif":<6} {"Staff":<6} {"Nom":<30}')
        self.stdout.write('-' * 80)
        for u in users:
            self.stdout.write(
                f'{u.username:<20} {u.profil:<16} {"oui" if u.is_active else "NON":<6} '
                f'{"oui" if u.is_staff else "non":<6} {u.nom_complet:<30}'
            )
