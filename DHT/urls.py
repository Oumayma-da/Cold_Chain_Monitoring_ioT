from django.urls import path
from django.views.generic import RedirectView

from . import api, views

urlpatterns = [
    # API existantes
    path("api/get", api.Dlist, name='json'),
    path("api/post", api.Dhtviews.as_view(), name='json_post'),

    # Nouvelles API pour l'affichage
    path("api/derniere/", api.derniere_mesure, name='api_derniere'),
    path("api/mesures/", api.mesures, name='api_mesures'),

    # Pages
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('graphique/<str:champ>/', views.graphique, name='graphique'),
    path('test/inserer/', views.inserer_test, name='inserer_test'),
    path('parametres/seuils/', views.modifier_seuils, name='modifier_seuils'),
]
