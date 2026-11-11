
from datetime import timedelta

import telebot

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Dht11, Seuil
from .serializers import DHT11serialize


# ---------------------------------------------------------
# API 1 : Récupérer toutes les mesures
# ---------------------------------------------------------
@api_view(['GET'])
def Dlist(request):
    all_data = Dht11.objects.all()
    data = DHT11serialize(all_data, many=True).data
    return Response({'data': data})


# ---------------------------------------------------------
# API 2 : Enregistrer une mesure + envoyer les alertes
# ---------------------------------------------------------
class Dhtviews(generics.CreateAPIView):
    queryset = Dht11.objects.all()
    serializer_class = DHT11serialize

    def perform_create(self, serializer):

        # 1. Enregistrer la mesure dans SQLite
        data = serializer.save()

        # 2. Récupérer la température
        temperature = data.temp

        # 3. Vérifier si la température dépasse 25 °C
        if temperature is not None and temperature > 25:

            message = f"Alerte IoT ! Température = {temperature} °C"

            # 4. Envoyer un email Gmail
            send_mail(
                subject="Alerte Température IoT",
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.EMAIL_HOST_USER],
                fail_silently=False
            )

            # 5. Envoyer un message Telegram
            bot = telebot.TeleBot(settings.TELEGRAM_TOKEN)

            bot.send_message(
                settings.TELEGRAM_CHAT_ID,
                message
            )


# ---------------------------------------------------------
# API 3 : Dernière mesure valide
# GET /api/derniere/
# ---------------------------------------------------------
@api_view(['GET'])
def derniere_mesure(request):

    mesure = (
        Dht11.objects
        .filter(
            temp__isnull=False,
            hum__isnull=False,
            dt__isnull=False
        )
        .order_by('-dt', '-id')
        .first()
    )

    if mesure is None:
        return Response({
            'mesure': None,
            'seuils': Seuil.tous()
        })

    return Response({
        'mesure': {
            'temp': mesure.temp,
            'hum': mesure.hum,
            'dt': mesure.dt,
        },
        'serveur_maintenant': timezone.now(),
        'seuils': Seuil.tous(),
    })


# ---------------------------------------------------------
# API 4 : Mesures filtrées + statistiques
# GET /api/mesures/?champ=temp&periode=24h
# ---------------------------------------------------------
PERIODES = {
    '1h': timedelta(hours=1),
    '24h': timedelta(hours=24),
    '7j': timedelta(days=7),
    '30j': timedelta(days=30),
}


@api_view(['GET'])
def mesures(request):

    champ = request.GET.get('champ')

    if champ not in ('temp', 'hum'):
        return Response(
            {
                'erreur': "Le paramètre champ doit être 'temp' ou 'hum'."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Garder uniquement les mesures valides
    qs = Dht11.objects.filter(
        dt__isnull=False,
        **{f'{champ}__isnull': False}
    )

    debut = parse_date(request.GET.get('debut') or '')
    fin = parse_date(request.GET.get('fin') or '')
    periode = request.GET.get('periode', '24h')

    if debut or fin:

        if debut:
            qs = qs.filter(dt__date__gte=debut)

        if fin:
            qs = qs.filter(dt__date__lte=fin)

        periode = 'personnalise'

    elif periode in PERIODES:

        qs = qs.filter(
            dt__gte=timezone.now() - PERIODES[periode]
        )

    else:
        periode = 'tout'

    qs = qs.order_by('dt', 'id')

    # Calculer les statistiques
    stats = qs.aggregate(
        min=Min(champ),
        max=Max(champ),
        moyenne=Avg(champ),
        nombre=Count('id')
    )

    # Récupérer les dates du minimum et maximum
    date_min = (
        qs.filter(**{champ: stats['min']})
        .values_list('dt', flat=True)
        .first()
        if stats['nombre'] else None
    )

    date_max = (
        qs.filter(**{champ: stats['max']})
        .values_list('dt', flat=True)
        .first()
        if stats['nombre'] else None
    )

    # Préparer les points pour les graphiques
    points = [
        {'dt': dt, 'v': v}
        for dt, v in qs.values_list('dt', champ)
    ]

    return Response({
        'champ': champ,
        'periode': periode,
        'stats': {
            'min': stats['min'],
            'max': stats['max'],
            'moyenne': (
                round(stats['moyenne'], 1)
                if stats['moyenne'] is not None
                else None
            ),
            'nombre': stats['nombre'],
            'date_min': date_min,
            'date_max': date_max,
        },
        'points': points,
    })
