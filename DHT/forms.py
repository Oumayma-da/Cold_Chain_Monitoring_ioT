from django import forms
from django.utils import timezone


class MesureTestForm(forms.Form):
    temp = forms.FloatField(
        label="Température (°C)",
        min_value=-40, max_value=80,
        widget=forms.NumberInput(attrs={'step': '0.1', 'placeholder': 'ex : 30'}),
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
#  Formulaire de modification des seuils (page Seuils)
# ---------------------------------------------------------
from .models import Seuil  # noqa: E402


class SeuilForm(forms.ModelForm):
    class Meta:
        model = Seuil
        fields = ['echelle_min', 'critique_min', 'attention_min',
                  'attention_max', 'critique_max', 'echelle_max']
        widgets = {nom: forms.NumberInput(attrs={'step': '0.1'}) for nom in fields}
