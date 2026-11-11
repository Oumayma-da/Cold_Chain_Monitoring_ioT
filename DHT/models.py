from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Dht11(models.Model):
    temp = models.FloatField(null=True)
    hum = models.FloatField(null=True)
    dt = models.DateTimeField(auto_now_add=True, null=True)

    # Texte affiché dans l'admin (au lieu de "Dht11 object (2)")
    def __str__(self):
        date = self.dt.strftime('%d/%m/%Y %H:%M') if self.dt else 'sans date'
        return f"{self.temp} °C / {self.hum} % — {date}"


class Seuil(models.Model):
    """Seuils min / max modifiables par l'admin (une ligne pour temp, une pour hum)."""

    CHAMPS = [('temp', 'Température'), ('hum', 'Humidité')]

    champ = models.CharField("Mesure", max_length=10, choices=CHAMPS, unique=True)
    valeur_min = models.FloatField("Minimum")
    valeur_max = models.FloatField("Maximum")
    modifie_le = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Seuil"
        verbose_name_plural = "Seuils"

    def __str__(self):
        return f"{self.get_champ_display()} : {self.valeur_min} à {self.valeur_max}"

    # Le minimum doit être plus petit que le maximum
    def clean(self):
        if self.valeur_min is not None and self.valeur_max is not None:
            if self.valeur_min >= self.valeur_max:
                raise ValidationError("Le minimum doit être plus petit que le maximum.")

    def en_dict(self):
        return {'min': self.valeur_min, 'max': self.valeur_max}

    @classmethod
    def obtenir(cls, champ):
        """Renvoie le seuil d'une mesure (créé avec les valeurs par défaut s'il n'existe pas)."""
        defaut = settings.SEUILS[champ]
        seuil, _ = cls.objects.get_or_create(
            champ=champ,
            defaults={'valeur_min': defaut['min'], 'valeur_max': defaut['max']},
        )
        return seuil

    @classmethod
    def tous(cls):
        """{'temp': {'min': 2, 'max': 8}, 'hum': {...}} : utilisé par les pages et les alertes."""
        return {champ: cls.obtenir(champ).en_dict() for champ, _ in cls.CHAMPS}
