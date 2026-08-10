from django.urls import path
from . import views

# Attention à l'ordre : les routes spécifiques (cf/, dtv/, resume/, tables/) doivent être
# déclarées avant la route générique '<zone>/<layer_type>/' (views.geo_layer), sinon celle-ci
# les intercepterait en interprétant leur premier segment comme un layer_type.
urlpatterns = [
    path('<str:zone>/tables/',          views.geo_tables,       name='geo-tables'),
    path('<str:zone>/resume/',          views.geo_resume,       name='geo-resume'),

    path('<str:zone>/cf/parcelles/',    views.geo_cf_parcelles, name='geo-cf-parcelles'),
    path('<str:zone>/cf/export/',       views.geo_cf_export,    name='geo-cf-export'),
    path('<str:zone>/cf/stats/',        views.geo_cf_stats,     name='geo-cf-stats'),
    path('<str:zone>/cf/detail/',       views.geo_cf_detail,    name='geo-cf-detail'),

    path('<str:zone>/dtv/villages/',    views.geo_dtv_villages, name='geo-dtv-villages'),
    path('<str:zone>/dtv/export/',      views.geo_dtv_export,   name='geo-dtv-export'),
    path('<str:zone>/dtv/stats/',       views.geo_dtv_stats,    name='geo-dtv-stats'),

    path('<str:zone>/<str:layer_type>/', views.geo_layer,       name='geo-layer'),
]
