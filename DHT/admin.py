from django.contrib import admin

from .models import Dht11, Seuil

# Titres de l'interface d'administration
admin.site.site_header = "Surveillance IoT — Administration"
admin.site.site_title = "Admin IoT"
admin.site.index_title = "Gestion des mesures"


@admin.register(Dht11)
class Dht11Admin(admin.ModelAdmin):
    # Colonnes affichées dans la liste
    list_display = ('id', 'temperature', 'humidite', 'date_mesure')
    # Filtre par date (colonne de droite)
    list_filter = ('dt',)
    # Navigation par année / mois / jour en haut de la liste
    date_hierarchy = 'dt'
    # Les plus récentes en premier
    ordering = ('-dt', '-id')
    # Nombre de lignes par page
    list_per_page = 50
    # Date en lecture seule (elle est remplie automatiquement)
    readonly_fields = ('dt',)

    # Noms de colonnes en français (sans modifier le modèle)
    @admin.display(description="Température (°C)", ordering='temp')
    def temperature(self, obj):
        return obj.temp

    @admin.display(description="Humidité (%)", ordering='hum')
    def humidite(self, obj):
        return obj.hum

    @admin.display(description="Date de la mesure", ordering='dt')
    def date_mesure(self, obj):
        return obj.dt


# Les seuils sont aussi modifiables depuis l'admin Django
@admin.register(Seuil)
class SeuilAdmin(admin.ModelAdmin):
    list_display = ('champ', 'critique_min', 'attention_min', 'attention_max', 'critique_max', 'modifie_le')
