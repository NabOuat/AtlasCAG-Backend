from rest_framework import serializers
from .models import (
    Dossier, EnqueteFonciere, Contrat, CertificationFonciere,
    HistoriqueStatutDossier, VagueEnvoi,
)


class DossierListSerializer(serializers.ModelSerializer):
    village_nom   = serializers.CharField(source='village.nom',  read_only=True)
    zone_nom      = serializers.CharField(source='zone.nom',     read_only=True)
    cree_par_nom  = serializers.SerializerMethodField()

    class Meta:
        model  = Dossier
        fields = [
            'id', 'numero_dossier', 'village', 'village_nom',
            'zone', 'zone_nom', 'type_dossier', 'statut',
            'cree_le', 'modifie_le', 'cree_par', 'cree_par_nom',
        ]

    def get_cree_par_nom(self, obj) -> str | None:
        if obj.cree_par:
            return f'{obj.cree_par.first_name} {obj.cree_par.last_name}'.strip() or obj.cree_par.username
        return None


class HistoriqueStatutSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.SerializerMethodField()

    class Meta:
        model  = HistoriqueStatutDossier
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'modifie_par_nom', 'modifie_le', 'commentaire']

    def get_modifie_par_nom(self, obj) -> str | None:
        if obj.modifie_par:
            return f'{obj.modifie_par.first_name} {obj.modifie_par.last_name}'.strip()
        return None


class DossierDetailSerializer(DossierListSerializer):
    historique = HistoriqueStatutSerializer(source='historique_statuts', many=True, read_only=True)

    class Meta(DossierListSerializer.Meta):
        fields = DossierListSerializer.Meta.fields + ['historique']


class DossierCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Dossier
        fields = ['numero_dossier', 'village', 'zone', 'type_dossier', 'statut']


class VagueEnvoiSerializer(serializers.ModelSerializer):
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)

    class Meta:
        model  = VagueEnvoi
        fields = ['id', 'nom', 'date', 'libelle', 'zone', 'zone_nom', 'type_dossier', 'cree_le']


class SuiviCFSerializer(serializers.ModelSerializer):
    """Vue de suivi administratif des dossiers CF (statut, statut_cf, vague d'envoi) —
    distincte de la table attributaire SIG exposée par apps.geo (cf/parcelles/)."""
    village_nom      = serializers.CharField(source='village.nom', read_only=True)
    zone_nom         = serializers.CharField(source='zone.nom',    read_only=True)
    cree_par_nom     = serializers.SerializerMethodField()
    vague_envoi_nom  = serializers.CharField(source='vague_envoi.nom', read_only=True, default=None)
    departement_nom          = serializers.SerializerMethodField()
    sous_prefecture_nom      = serializers.SerializerMethodField()
    controle_qualite_statut  = serializers.SerializerMethodField()

    class Meta:
        model  = Dossier
        fields = [
            'id', 'numero_dossier', 'village', 'village_nom', 'zone', 'zone_nom',
            'departement_nom', 'sous_prefecture_nom', 'statut', 'statut_cf', 'statut_publicite',
            'controle_qualite_statut', 'vague_envoi', 'vague_envoi_nom',
            'num_demand', 'numero_parcelle', 'nom_demandeur', 'superficie_parcelle', 'perimetre_parcelle',
            'nom_ota', 'n_demcge', 'nom_ce', 'observation', 'cree_le', 'modifie_le', 'cree_par', 'cree_par_nom',
        ]

    def get_cree_par_nom(self, obj) -> str | None:
        if obj.cree_par:
            return f'{obj.cree_par.first_name} {obj.cree_par.last_name}'.strip() or obj.cree_par.username
        return None

    def get_departement_nom(self, obj) -> str | None:
        sp = obj.village.sous_prefecture_fk
        return sp.departement.nom if sp and sp.departement else None

    def get_sous_prefecture_nom(self, obj) -> str | None:
        # Même logique de repli que apps.referentiel.VillageListSerializer.get_sous_prefecture_nom :
        # préfère la FK (donnée référentiel structurée) au texte libre legacy, qui peut diverger.
        sp = obj.village.sous_prefecture_fk
        return sp.nom if sp else obj.village.sous_prefecture

    def get_controle_qualite_statut(self, obj) -> str | None:
        # Résultat du contrôle qualité (apps.controle.ControleQualite) — indépendant du
        # workflow métier (statut_publicite) : jamais l'un ne dérive de l'autre.
        from apps.controle.models import ControleQualite
        dernier = ControleQualite.objects.filter(dossier=obj).order_by('-cree_le').first()
        return dernier.statut if dernier and dernier.statut in ('VALIDE', 'REJETE') else None


class SuiviCFCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Dossier
        fields = [
            'numero_dossier', 'village', 'zone', 'statut', 'statut_cf', 'vague_envoi',
            'num_demand', 'numero_parcelle', 'nom_demandeur', 'superficie_parcelle', 'perimetre_parcelle',
            'nom_ota', 'n_demcge', 'nom_ce', 'observation',
        ]
