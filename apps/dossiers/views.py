from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Dossier
from .serializers import DossierListSerializer, DossierDetailSerializer, DossierCreateSerializer


class DossierViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Dossier.objects.select_related('village', 'zone', 'cree_par').order_by('-cree_le')
        zone         = self.request.query_params.get('zone')
        statut       = self.request.query_params.get('statut')
        type_dossier = self.request.query_params.get('type_dossier')
        search       = self.request.query_params.get('search')
        if zone:         qs = qs.filter(zone__id=zone)
        if statut:       qs = qs.filter(statut=statut)
        if type_dossier: qs = qs.filter(type_dossier=type_dossier)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(numero_dossier__icontains=search) | Q(village__nom__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return DossierCreateSerializer
        if self.action == 'retrieve':
            return DossierDetailSerializer
        return DossierListSerializer

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total':    qs.count(),
            'en_cours': qs.filter(statut='EN_COURS').count(),
            'valide':   qs.filter(statut='VALIDE').count(),
            'rejete':   qs.filter(statut='REJETE').count(),
            'archive':  qs.filter(statut='ARCHIVE').count(),
            'par_type': {
                'DTV':                qs.filter(type_dossier='DTV').count(),
                'CF':                 qs.filter(type_dossier='CF').count(),
                'CONTRACTUALISATION': qs.filter(type_dossier='CONTRACTUALISATION').count(),
            },
        })
