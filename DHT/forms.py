from django import forms
from django.utils import timezone

from .models import Seuil


# ---------------------------------------------------------
#  Insertion d'une mesure de test (admin)
# ---------------------------------------------------------
class MesureTestForm(forms.Form):
    temp = forms.FloatField(
        label="Température (°C)",
        min_value=-40, max_value=80,
        widget=forms.NumberInput(attrs={'step': '0.1', 'placeholder': 'ex : 9'}),
    )
    hum = forms.FloatField(
        label="Humidité (%)",
        min_value=0, max_value=100,
        widget=forms.NumberInput(attrs={'step': '0.1', 'placeholder': 'ex : 55'}),
    )
    # Facultatif : pour simuler une mesure dans le passé
    dt = forms.DateTimeField(
        label="Date de la mesure (facultatif)",
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Laisse vide pour utiliser la date et l'heure actuelles.",
    )

    def clean_dt(self):
        dt = self.cleaned_data.get('dt')
        if dt and dt > timezone.now():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return dt


# ---------------------------------------------------------
#  Modification des seuils (page Seuils)
# ---------------------------------------------------------
class SeuilForm(forms.ModelForm):
    class Meta:
        model = Seuil
        fields = ['valeur_min', 'valeur_max']
        widgets = {
            'valeur_min': forms.NumberInput(attrs={'step': '0.1'}),
            'valeur_max': forms.NumberInput(attrs={'step': '0.1'}),
        }


# ---------------------------------------------------------
#  NOUVEAU : Incidents
# ---------------------------------------------------------
class CommentaireForm(forms.Form):
    texte = forms.CharField(
        label="Commentaire",
        max_length=1000,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': "Ex : J'ai vérifié la porte du frigo, elle était mal fermée."}),
    )


class ClotureForm(forms.Form):
    raison = forms.CharField(
        label="Raison de la clôture",
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': "Ex : Cause identifiée (porte ouverte), catalyseurs vérifiés."}),
    )
