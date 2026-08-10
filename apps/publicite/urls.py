from django.urls import path
from . import views

urlpatterns = [
    path('dossiers/<int:dossier_id>/mettre-en-publicite/', views.MettreEnPubliciteView.as_view(), name='publicite-mettre-en-publicite'),
    path('dossiers/<int:dossier_id>/approuver/',            views.ApprouverView.as_view(),         name='publicite-approuver'),
    path('dossiers/<int:dossier_id>/rejeter/',               views.RejeterView.as_view(),           name='publicite-rejeter'),
    path('dossiers/<int:dossier_id>/valider/',                views.ValiderView.as_view(),           name='publicite-valider'),
    path('dossiers/<int:dossier_id>/historique/',             views.HistoriqueMigrationView.as_view(), name='publicite-historique'),
]
