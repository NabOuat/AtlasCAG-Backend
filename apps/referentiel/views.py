from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Zone, Region, SousPrefecture, Village
from .serializers import ZoneSerializer, RegionSerializer, SousPrefectureSerializer, VillageListSerializer


class ZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Zone.objects.all().order_by('nom')
    serializer_class   = ZoneSerializer
    permission_classes = [permissions.IsAuthenticated]


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Region.objects.all().order_by('nom')
    serializer_class   = RegionSerializer
    permission_classes = [permissions.IsAuthenticated]


class VillageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = VillageListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs    = Village.objects.select_related('zone', 'sous_prefecture_fk').order_by('nom')
        zone  = self.request.query_params.get('zone')
        sp    = self.request.query_params.get('sous_prefecture')
        etape = self.request.query_params.get('etape')
        if zone:  qs = qs.filter(zone__id=zone)
        if sp:    qs = qs.filter(sous_prefecture__icontains=sp)
        if etape == 'VALIDE':      qs = qs.filter(valide=True)
        elif etape == 'APPROUVE':  qs = qs.filter(approuve=True, valide=False)
        elif etape == 'DELIMITE':  qs = qs.filter(delimite=True, approuve=False)
        elif etape == 'NON_DEMARRE': qs = qs.filter(recueil_historique_fait=False)
        return qs

    @action(detail=False, methods=['get'])
    def stats_dtv(self, request):
        qs = Village.objects.all()
        zone = request.query_params.get('zone')
        if zone: qs = qs.filter(zone__id=zone)
        return Response({
            'total':          qs.count(),
            'valide':         qs.filter(valide=True).count(),
            'approuve':       qs.filter(approuve=True).count(),
            'delimite':       qs.filter(delimite=True).count(),
            'pub_ouverte':    qs.filter(publicite_ouverte=True).count(),
            'pub_cloturee':   qs.filter(publicite_cloturee=True).count(),
            'non_demarre':    qs.filter(recueil_historique_fait=False).count(),
        })
