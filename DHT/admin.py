from django import forms
from django.contrib import admin

from .models import Dht11, Evenement, Incident, Operateur, Seuil

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
    list_display = ('champ', 'valeur_min', 'valeur_max', 'modifie_le')


# =========================================================
#  NOUVEAU : Opérateurs, incidents et journal
# =========================================================
class OperateurForm(forms.ModelForm):
    """Formulaire de l'opérateur : on peut aussi modifier son email (stocké dans le compte utilisateur)."""
    email = forms.EmailField(label="Email (alertes Gmail)", required=False)

    class Meta:
        model = Operateur
        fields = ['user', 'niveau', 'email', 'telegram_chat_id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        operateur = super().save(commit)
        operateur.user.email = self.cleaned_data.get('email', '')
        operateur.user.save()
        return operateur


@admin.register(Operateur)
class OperateurAdmin(admin.ModelAdmin):
    form = OperateurForm
    list_display = ('niveau', 'user', 'email', 'telegram_chat_id')

    @admin.display(description="Email")
    def email(self, obj):
        return obj.user.email or "— (email du .env utilisé)"


class EvenementInline(admin.TabularInline):
    model = Evenement
    extra = 0
    fields = ('date', 'type', 'operateur', 'auteur', 'message')
    readonly_fields = fields
    can_delete = False


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'statut', 'debut', 'fin', 'compteur', 'niveau_atteint', 'temp_max')
    list_filter = ('statut',)
    inlines = [EvenementInline]
