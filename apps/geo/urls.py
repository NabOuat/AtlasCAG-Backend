from django.urls import path
from . import views

urlpatterns = [
    path('<str:zone>/tables/',          views.geo_tables,       name='geo-tables'),
    path('<str:zone>/cf/parcelles/',    views.geo_cf_parcelles, name='geo-cf-parcelles'),
    path('<str:zone>/cf/detail/',       views.geo_cf_detail,    name='geo-cf-detail'),
    path('<str:zone>/<str:layer_type>/', views.geo_layer,       name='geo-layer'),
]
