from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =========================================================
#  MESURES DU CAPTEUR
# =========================================================
class Dht11(models.Model):
    temp = models.FloatField(null=True)
    hum = models.FloatField(null=True)
    dt = models.DateTimeField(auto_now_add=True, null=True)

    # Texte affiché dans l'admin (au lieu de "Dht11 object (2)")
    def __str__(self):
        date = self.dt.strftime('%d/%m/%Y %H:%M') if self.dt else 'sans date'
        return f"{self.temp} °C / {self.hum} % — {date}"


# =========================================================
#  SEUILS (modifiables par l'admin)
# =========================================================
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


# =========================================================
#  OPÉRATEURS (hiérarchie : Opérateur 1 -> 2 -> 3)
# =========================================================
class Operateur(models.Model):
    NIVEAUX = [(1, 'Opérateur 1'), (2, 'Opérateur 2'), (3, 'Opérateur 3')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operateur',
                                verbose_name="Compte utilisateur")
    niveau = models.PositiveSmallIntegerField("Niveau", choices=NIVEAUX, unique=True)
    telegram_chat_id = models.CharField("Chat ID Telegram", max_length=50, blank=True,
                                        help_text="Laisse vide si l'opérateur n'utilise pas Telegram.")

    class Meta:
        verbose_name = "Opérateur"
        verbose_name_plural = "Opérateurs"
        ordering = ['niveau']

    def __str__(self):
        return f"{self.get_niveau_display()} ({self.user.username})"


# =========================================================
#  INCIDENTS
# =========================================================
class Incident(models.Model):
    OUVERT = 'ouvert'
    RESOLU = 'resolu'
    CLOTURE = 'cloture'
    STATUTS = [
        (OUVERT, 'En cours'),
        (RESOLU, 'Résolu'),        # la température est revenue dans la plage
        (CLOTURE, 'Clôturé'),      # l'admin a fermé le dossier
    ]

    statut = models.CharField("État", max_length=10, choices=STATUTS, default=OUVERT)
    debut = models.DateTimeField("Date début")
    fin = models.DateTimeField("Date fin", null=True, blank=True)
    cloture_le = models.DateTimeField("Clôturé le", null=True, blank=True)

    compteur = models.PositiveIntegerField("Compteur d'alertes", default=0)
    niveau_atteint = models.PositiveSmallIntegerField("Niveau atteint", default=0)
    temp_max = models.FloatField("Température maximale", null=True)
    temp_min = models.FloatField("Température minimale", null=True)

    # Seuils au moment de l'ouverture (preuve, même si l'admin les change après)
    seuil_min = models.FloatField("Seuil min à l'ouverture")
    seuil_max = models.FloatField("Seuil max à l'ouverture")

    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        ordering = ['-debut']

    def __str__(self):
        return f"Incident #{self.pk} ({self.get_statut_display()})"

    @property
    def est_ouvert(self):
        return self.statut == self.OUVERT

    @property
    def duree(self):
        """Durée de l'incident (jusqu'à maintenant s'il est encore ouvert)."""
        return (self.fin or timezone.now()) - self.debut

    @property
    def duree_texte(self):
        minutes = int(self.duree.total_seconds() // 60)
        heures, minutes = divmod(minutes, 60)
        jours, heures = divmod(heures, 24)
        if jours:
            return f"{jours} j {heures} h {minutes:02d} min"
        if heures:
            return f"{heures} h {minutes:02d} min"
        return f"{minutes} min"


# =========================================================
#  JOURNAL DE L'INCIDENT (tout ce qui se passe, dans l'ordre)
#  -> contient aussi les accusés de réception et les commentaires
# =========================================================
class Evenement(models.Model):
    OUVERTURE = 'ouverture'
    MESURE = 'mesure'
    ALERTE = 'alerte'
    ESCALADE = 'escalade'
    ACCUSE = 'accuse'
    COMMENTAIRE = 'commentaire'
    RESOLUTION = 'resolution'
    CLOTURE = 'cloture'
    TYPES = [
        (OUVERTURE, 'Ouverture'),
        (MESURE, 'Mesure hors limites'),
        (ALERTE, 'Alerte envoyée'),
        (ESCALADE, 'Escalade'),
        (ACCUSE, 'Accusé de réception'),
        (COMMENTAIRE, 'Commentaire'),
        (RESOLUTION, 'Retour à la normale'),
        (CLOTURE, 'Clôture'),
    ]

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='evenements')
    date = models.DateTimeField("Date", default=timezone.now)
    type = models.CharField("Type", max_length=15, choices=TYPES)
    message = models.TextField("Détail")
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name="Auteur")
    operateur = models.ForeignKey(Operateur, on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="Opérateur concerné")
    valeur = models.FloatField("Température", null=True, blank=True)

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Journal des incidents"
        ordering = ['date', 'id']

    def __str__(self):
        return f"#{self.incident_id} — {self.get_type_display()} — {self.date:%d/%m/%Y %H:%M}"
