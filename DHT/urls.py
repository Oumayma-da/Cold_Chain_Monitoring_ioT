from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import api, views

urlpatterns = [
    # API (l'ESP envoie sur api/post)
    path("api/get", api.Dlist, name='json'),
    path("api/post", api.Dhtviews.as_view(), name='json_post'),
    path("api/derniere/", api.derniere_mesure, name='api_derniere'),
    path("api/mesures/", api.mesures, name='api_mesures'),

    # Export CSV des mesures (même filtre que le graphique)
    path("export/mesures.csv", api.export_mesures_csv, name='export_mesures_csv'),

    # Pages
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('graphique/<str:champ>/', views.graphique, name='graphique'),
    path('test/inserer/', views.inserer_test, name='inserer_test'),
    path('parametres/seuils/', views.modifier_seuils, name='modifier_seuils'),

    # Incidents
    path('incidents/', views.liste_incidents, name='liste_incidents'),
    path('incidents/<int:pk>/', views.incident_detail, name='incident_detail'),
    path('incidents/<int:pk>/fiche.pdf', views.export_fiche_pdf, name='export_fiche_pdf'),

    # Connexion des opérateurs
    path('connexion/', auth_views.LoginView.as_view(template_name='DHT/connexion.html'), name='connexion'),
    path('deconnexion/', auth_views.LogoutView.as_view(), name='deconnexion'),
]
