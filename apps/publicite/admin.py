from django.contrib import admin
from .models import HistoriqueMigrationCouche


@admin.register(HistoriqueMigrationCouche)
class HistoriqueMigrationCoucheAdmin(admin.ModelAdmin):
    list_display  = ['num_demand', 'ancien_statut', 'nouveau_statut', 'succes', 'date_migration', 'effectue_par']
    list_filter    = ['succes', 'nouveau_statut']
    search_fields  = ['num_demand', 'dossier__numero_dossier']
