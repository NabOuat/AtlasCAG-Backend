from django.db import models
from apps.referentiel.models import Village, Zone


class VagueEnvoi(models.Model):
    """Lot de dossiers CF ou DTV envoyés ensemble pour traitement administratif."""

    TYPE_CHOICES = [
        ('CF',  'Certificat Foncier Rural'),
        ('DTV', 'Délimitation Territoire Villageois'),
    ]

    nom          = models.CharField(max_length=100)
    date         = models.DateField()
    libelle      = models.TextField(blank=True)
    zone         = models.ForeignKey(Zone, on_delete=models.RESTRICT, related_name='vagues_envoi')
    type_dossier = models.CharField(max_length=10, choices=TYPE_CHOICES)
    cree_le      = models.DateTimeField(auto_now_add=True)
    modifie_le   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vague_envoi'
        ordering = ['-date']

    def __str__(self):
        return f"{self.nom} — {self.zone} {self.type_dossier} ({self.date})"


class Dossier(models.Model):
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('VALIDE',   'Validé'),
        ('REJETE',   'Rejeté'),
        ('ARCHIVE',  'Archivé'),
        ('ANNULE',   'Annulé'),
    ]
    TYPE_CHOICES = [
        ('DTV',                'Délimitation territoire villageois'),
        ('CF',                 'Certificat foncier rural'),
        ('CONTRACTUALISATION', 'Contractualisation'),
    ]
    STATUT_CF_CHOICES = [
        ('LEVE',             'Relevé terrain'),
        ('PROV',             'Provisoire'),
        ('EN_PUBLICITE',     'En publicité'),
        ('APRES_PUBLICITE',  'Après publicité'),
        ('DEF',              'Définitif'),
        ('REJETE',           'Rejeté'),
    ]

    # ── Identité ──────────────────────────────────────────
    numero_dossier = models.CharField(max_length=50, unique=True, db_index=True)
    village        = models.ForeignKey(Village, on_delete=models.RESTRICT, related_name='dossiers')
    zone           = models.ForeignKey(Zone,    on_delete=models.RESTRICT, related_name='dossiers')
    type_dossier   = models.CharField(max_length=20, choices=TYPE_CHOICES)
    statut         = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    cree_le        = models.DateTimeField(auto_now_add=True)
    modifie_le     = models.DateTimeField(auto_now=True)
    cree_par       = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='dossiers_crees',
    )
    vague_envoi    = models.ForeignKey(
        VagueEnvoi, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='dossiers',
    )

    # ── Données CF (Certificat Foncier Rural) ─────────────
    num_demand          = models.CharField(max_length=50,  blank=True)  # NUM_DEMAND QGIS
    nom_demandeur       = models.CharField(max_length=150, blank=True)  # NOM_DEM
    superficie_parcelle = models.FloatField(null=True, blank=True)      # SUPERF (ha)
    perimetre_parcelle  = models.FloatField(null=True, blank=True)      # PERIM (m)
    ocs                 = models.CharField(max_length=100, blank=True)  # Occupation du sol
    nom_ota             = models.CharField(max_length=100, blank=True)  # Opérateur agréé
    n_demcge            = models.CharField(max_length=50,  blank=True)  # N° demande CGE
    boucle              = models.CharField(max_length=50,  blank=True)
    cd_sp_vil           = models.CharField(max_length=50,  blank=True)
    clas_preci          = models.CharField(max_length=10,  blank=True)
    point_ratt          = models.CharField(max_length=100, blank=True)
    statut_cf           = models.CharField(
        max_length=20, choices=STATUT_CF_CHOICES,
        null=True, blank=True,
    )

    class Meta:
        db_table = 'dossier'

    def __str__(self):
        return self.numero_dossier


class SommetParcelle(models.Model):
    """Point GPS relevé sur la limite d'une parcelle CF."""

    STATUT_CHOICES = [
        ('LEVE', 'Relevé terrain'),
        ('PROV', 'Provisoire'),
    ]

    dossier    = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='sommets')
    statut     = models.CharField(max_length=10, choices=STATUT_CHOICES, default='LEVE')
    num_sommet = models.CharField(max_length=20, blank=True)
    typ_sommet = models.CharField(max_length=30, blank=True)
    typ_leve   = models.CharField(max_length=30, blank=True)
    coord_x    = models.FloatField()                                # longitude WGS84
    coord_y    = models.FloatField()                                # latitude  WGS84
    prec_gnss  = models.FloatField(null=True, blank=True)
    clas_preci = models.CharField(max_length=10,  blank=True)
    amorce     = models.BooleanField(default=False)
    nom_agent  = models.CharField(max_length=100, blank=True)
    nom_vois   = models.CharField(max_length=150, blank=True)
    typ_vois   = models.CharField(max_length=50,  blank=True)
    typ_nat    = models.CharField(max_length=50,  blank=True)
    num_tronc  = models.CharField(max_length=20,  blank=True)
    boucle     = models.CharField(max_length=50,  blank=True)
    cd_sp_vil  = models.CharField(max_length=50,  blank=True)
    point_ratt = models.CharField(max_length=100, blank=True)
    distance   = models.FloatField(null=True, blank=True)          # DISTANCE (Prov)
    date_crea  = models.DateField(null=True, blank=True)
    date_maj   = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'sommet_parcelle'
        ordering = ['dossier', 'num_sommet']

    def __str__(self):
        return f"{self.dossier.numero_dossier} — S{self.num_sommet}"


class EnqueteFonciere(models.Model):
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('TERMINE',  'Terminé'),
    ]
    dossier      = models.OneToOneField(Dossier, on_delete=models.CASCADE, related_name='enquete')
    date_debut   = models.DateField(null=True, blank=True)
    date_fin     = models.DateField(null=True, blank=True)
    statut       = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    observations = models.TextField(blank=True)

    class Meta:
        db_table = 'enquete_fonciere'


class Contrat(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('SIGNE',     'Signé'),
        ('ANNULE',    'Annulé'),
    ]
    dossier        = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='contrats')
    asf            = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='contrats_rediges',
    )
    date_signature = models.DateField(null=True, blank=True)
    statut         = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    observations   = models.TextField(blank=True)

    class Meta:
        db_table = 'contrat'


class CertificationFonciere(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('DELIVREE',   'Délivrée'),
        ('SUSPENDUE',  'Suspendue'),
    ]
    dossier         = models.OneToOneField(Dossier, on_delete=models.CASCADE, related_name='certification')
    numero_cf       = models.CharField(max_length=50, unique=True, null=True, blank=True)
    date_delivrance = models.DateField(null=True, blank=True)
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')

    class Meta:
        db_table = 'certification_fonciere'


class HistoriqueStatutDossier(models.Model):
    dossier        = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='historique_statuts')
    ancien_statut  = models.CharField(max_length=20)
    nouveau_statut = models.CharField(max_length=20)
    modifie_par    = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='modifications_statut',
    )
    modifie_le  = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        db_table = 'historique_statut_dossier'
        ordering = ['-modifie_le']
