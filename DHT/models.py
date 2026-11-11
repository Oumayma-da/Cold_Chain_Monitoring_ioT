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
    """Seuils modifiables par l'admin (une ligne pour temp, une ligne pour hum)."""

    CHAMPS = [('temp', 'Température'), ('hum', 'Humidité')]

    champ = models.CharField("Mesure", max_length=10, choices=CHAMPS, unique=True)
    critique_min = models.FloatField("Critique en dessous de")
    attention_min = models.FloatField("Attention en dessous de")
    attention_max = models.FloatField("Attention au-dessus de")
    critique_max = models.FloatField("Critique au-dessus de")
    echelle_min = models.FloatField("Début de la jauge")
    echelle_max = models.FloatField("Fin de la jauge")
    modifie_le = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Seuil"
        verbose_name_plural = "Seuils"

    def __str__(self):
        return f"Seuils {self.get_champ_display()}"

    # Vérifie que les valeurs sont dans le bon ordre
    def clean(self):
        valeurs = [self.echelle_min, self.critique_min, self.attention_min,
                   self.attention_max, self.critique_max, self.echelle_max]
        if None in valeurs:
            return
        if not (self.echelle_min <= self.critique_min <= self.attention_min
                < self.attention_max <= self.critique_max <= self.echelle_max):
            raise ValidationError(
                "Ordre obligatoire : début jauge ≤ critique min ≤ attention min "
                "< attention max ≤ critique max ≤ fin jauge."
            )

    def en_dict(self):
        return {
            'critique_min': self.critique_min, 'attention_min': self.attention_min,
            'attention_max': self.attention_max, 'critique_max': self.critique_max,
            'echelle_min': self.echelle_min, 'echelle_max': self.echelle_max,
        }

    @classmethod
    def obtenir(cls, champ):
        """Renvoie le seuil d'une mesure. S'il n'existe pas encore,
        il est créé avec les valeurs par défaut de settings.SEUILS."""
        seuil, _ = cls.objects.get_or_create(champ=champ, defaults=settings.SEUILS[champ])
        return seuil

    @classmethod
    def tous(cls):
        """{'temp': {...}, 'hum': {...}} : utilisé par les pages et (étape C) les alertes."""
        return {champ: cls.obtenir(champ).en_dict() for champ, _ in cls.CHAMPS}