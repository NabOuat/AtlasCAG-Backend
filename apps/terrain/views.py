from rest_framework import viewsets, permissions
from .models import PlanningASFJournalier, Layon
from .serializers import PlanningSerializer, PlanningCreateSerializer, LayonSerializer


class PlanningViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = PlanningASFJournalier.objects.select_related('asf', 'village__zone').order_by('date_activite', 'heure_debut')
        asf           = self.request.query_params.get('asf')
        zone          = self.request.query_params.get('zone')
        date_debut    = self.request.query_params.get('date_debut')
        date_fin      = self.request.query_params.get('date_fin')
        type_activite = self.request.query_params.get('type_activite')
        if asf:           qs = qs.filter(asf__id=asf)
        if zone:          qs = qs.filter(village__zone__id=zone)
        if date_debut:    qs = qs.filter(date_activite__gte=date_debut)
        if date_fin:      qs = qs.filter(date_activite__lte=date_fin)
        if type_activite: qs = qs.filter(type_activite=type_activite)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return PlanningCreateSerializer
        return PlanningSerializer


class LayonViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = LayonSerializer

    def get_queryset(self):
        qs      = Layon.objects.select_related('village__zone').order_by('village__nom', 'identifiant')
        village = self.request.query_params.get('village')
        if village: qs = qs.filter(village__id=village)
        return qs
