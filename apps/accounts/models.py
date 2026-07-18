from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class UtilisateurManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError('Le nom d\'utilisateur est obligatoire')
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('profil', 'CHEF_PROJET')
        return self.create_user(username, password, **extra)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    PROFILS = [
        ('CET',          'Chef d\'Équipe Technique'),
        ('AGENT_GNSS',   'Agent GNSS'),
        ('CE',           'Commissaire-Enquêteur'),
        ('CR',           'Coordonnateur Régional'),
        ('SIFOR_JUNIOR', 'SIFOR Junior'),
        ('SIFOR_SENIOR', 'SIFOR Senior'),
        ('RAF',          'Responsable Administratif et Financier'),
        ('CHEF_PROJET',  'Chef de Projet'),
    ]

    username    = models.CharField(max_length=150, unique=True)
    first_name  = models.CharField(max_length=150, blank=True)
    last_name   = models.CharField(max_length=150, blank=True)
    email       = models.EmailField(blank=True)
    profil      = models.CharField(max_length=20, choices=PROFILS)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Zone principale et hiérarchie
    zone_principale  = models.ForeignKey(
        'referentiel.Zone', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='agents_principaux'
    )
    superieur = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='subordonnes'
    )

    objects = UtilisateurManager()

    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = ['profil']

    class Meta:
        db_table = 'utilisateur'
        verbose_name = 'Utilisateur'

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.profil})'

    @property
    def nom_complet(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.username

