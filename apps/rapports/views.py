from rest_framework import viewsets, permissions
from .models import RapportPeriodique
from .serializers import RapportSerializer


class RapportViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = RapportSerializer

    def get_queryset(self):
        qs = RapportPeriodique.objects.select_related('zone', 'redige_par').order_by('-cree_le')
        zone         = self.request.query_params.get('zone')
        type_rapport = self.request.query_params.get('type_rapport')
        statut       = self.request.query_params.get('statut')
        periode      = self.request.query_params.get('periode')
        if zone:         qs = qs.filter(zone__id=zone)
        if type_rapport: qs = qs.filter(type_rapport=type_rapport)
        if statut:       qs = qs.filter(statut=statut)
        if periode:      qs = qs.filter(periode=periode)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        serializer.save(redige_par=self.request.user)
