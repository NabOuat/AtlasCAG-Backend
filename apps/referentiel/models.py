from django.db import models


class Zone(models.Model):
    TYPE_CHOICES = [('TECHNIQUE', 'Zone technique'), ('REGIONALE', 'Zone régionale')]
    nom  = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TECHNIQUE')

    class Meta:
        db_table = 'zone'

    def __str__(self):
        return self.nom


class Region(models.Model):
    nom  = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'region'

    def __str__(self):
        return self.nom


class Departement(models.Model):
    nom    = models.CharField(max_length=150)
    region = models.ForeignKey(Region, on_delete=models.RESTRICT, related_name='departements')

    class Meta:
        db_table        = 'departement'
        unique_together = ('nom', 'region')

    def __str__(self):
        return self.nom


class SousPrefecture(models.Model):
    nom         = models.CharField(max_length=150)
    departement = models.ForeignKey(Departement, on_delete=models.RESTRICT, related_name='sous_prefectures')

    class Meta:
        db_table        = 'sous_prefecture'
        unique_together = ('nom', 'departement')

    def __str__(self):
        return self.nom


class Village(models.Model):
    """Entité administrative pure — sans données de processus DTV."""

    nom                = models.CharField(max_length=150)
    sous_prefecture    = models.CharField(max_length=150)   # legacy VARCHAR
    sous_prefecture_fk = models.ForeignKey(
        SousPrefecture, null=True, blank=True,
        on_delete=models.RESTRICT, related_name='villages',
        db_column='sous_prefecture_id',
    )
    zone      = models.ForeignKey(Zone, on_delete=models.RESTRICT, related_name='villages')
    latitude  = models.FloatField(null=True, blank=True)    # centroïde, dérivé du DTV
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        db_table        = 'village'
        unique_together = ('nom', 'sous_prefecture', 'zone')

    def __str__(self):
        return self.nom


class DTV(models.Model):
    """Délimitation du Territoire Villageois — processus et données spatiales."""

    STATUT_CHOICES = [
        ('NON_DEMARRE', 'Non démarré'),
        ('EN_COURS',    'En cours'),
        ('PROVISOIRE',  'Provisoire'),
        ('APPROUVE',    'Approuvé'),
        ('VALIDE',      'Validé'),
    ]

    village    = models.OneToOneField(Village, on_delete=models.CASCADE, related_name='dtv')
    statut     = models.CharField(max_length=20, choices=STATUT_CHOICES, default='NON_DEMARRE')

    # ── Progression DTV (8 étapes) ────────────────────────
    recueil_historique_fait = models.BooleanField(default=False)
    layons_identifies       = models.IntegerField(default=0)
    pv_constat_signes       = models.IntegerField(default=0)
    delimite                = models.BooleanField(default=False)
    publicite_ouverte       = models.BooleanField(default=False)
    publicite_cloturee      = models.BooleanField(default=False)
    approuve                = models.BooleanField(default=False)
    valide                  = models.BooleanField(default=False)

    # ── Données spatiales ─────────────────────────────────
    superficie  = models.FloatField(null=True, blank=True)          # SUPERF (ha)
    perimetre   = models.FloatField(null=True, blank=True)          # PERIM  (m)
    nom_ota     = models.CharField(max_length=100, blank=True)      # NOM_OTA
    clas_preci  = models.CharField(max_length=10,  blank=True)      # A / B / C
    prec_gnss   = models.FloatField(null=True, blank=True)          # m
    boucle      = models.CharField(max_length=50,  blank=True)
    cd_sp_vil   = models.CharField(max_length=50,  blank=True)
    point_ratt  = models.CharField(max_length=100, blank=True)

    # ── Dates ─────────────────────────────────────────────
    date_debut      = models.DateField(null=True, blank=True)
    date_validation = models.DateField(null=True, blank=True)
    cree_le         = models.DateTimeField(auto_now_add=True)
    modifie_le      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dtv'

    def __str__(self):
        return f"DTV — {self.village.nom} ({self.statut})"


class SommetVillage(models.Model):
    """Point GPS relevé sur la limite du territoire villageois."""

    STATUT_CHOICES = [
        ('LEVE',  'Relevé terrain'),
        ('PROV',  'Provisoire'),
        ('VALIDE','Validé'),
    ]

    dtv        = models.ForeignKey(DTV, on_delete=models.CASCADE, related_name='sommets')
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
    date_crea  = models.DateField(null=True, blank=True)
    date_maj   = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'sommet_village'
        ordering = ['dtv', 'num_sommet']

    def __str__(self):
        return f"{self.dtv.village.nom} — S{self.num_sommet}"
