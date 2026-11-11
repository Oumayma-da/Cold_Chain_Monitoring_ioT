from datetime import timedelta

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
#  API existantes (on ne les touche pas)
# ---------------------------------------------------------
@api_view(['GET'])
def Dlist(request):
    all_data = Dht11.objects.all()
    data = DHT11serialize(all_data, many=True).data
    return Response({'data': data})


class Dhtviews(generics.CreateAPIView):
    queryset = Dht11.objects.all()
    serializer_class = DHT11serialize


# ---------------------------------------------------------
#  NOUVEAU (A2) : dernière mesure valide pour les cartes
#  GET /api/derniere/
# ---------------------------------------------------------
@api_view(['GET'])
def derniere_mesure(request):
    # On ignore les lignes vides (temp ou hum = null)
    mesure = (
        Dht11.objects
        .filter(temp__isnull=False, hum__isnull=False, dt__isnull=False)
        .order_by('-dt', '-id')
        .first()
    )
    if mesure is None:
        return Response({'mesure': None, 'seuils': Seuil.tous()})

    return Response({
        'mesure': {
            'temp': mesure.temp,
            'hum': mesure.hum,
            'dt': mesure.dt,
        },
        'serveur_maintenant': timezone.now(),
        'seuils': Seuil.tous(),   # pour suivre les changements de seuils sans recharger
    })


# ---------------------------------------------------------
#  NOUVEAU (A3 + A4) : mesures filtrées + statistiques pour les graphiques
#  GET /api/mesures/?champ=temp&periode=24h
#  GET /api/mesures/?champ=hum&debut=2026-11-01&fin=2026-11-05
#  periode : 1h | 24h | 7j | 30j | tout
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
            {'erreur': "Le paramètre champ doit être 'temp' ou 'hum'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # On garde seulement les lignes où la valeur existe
    qs = Dht11.objects.filter(dt__isnull=False, **{f'{champ}__isnull': False})

    debut = parse_date(request.GET.get('debut') or '')
    fin = parse_date(request.GET.get('fin') or '')
    periode = request.GET.get('periode', '24h')

    if debut or fin:
        # Filtre personnalisé par dates (jours inclus)
        if debut:
            qs = qs.filter(dt__date__gte=debut)
        if fin:
            qs = qs.filter(dt__date__lte=fin)
        periode = 'personnalise'
    elif periode in PERIODES:
        qs = qs.filter(dt__gte=timezone.now() - PERIODES[periode])
    else:
        periode = 'tout'

    qs = qs.order_by('dt', 'id')

    # Statistiques calculées par la base de données
    stats = qs.aggregate(min=Min(champ), max=Max(champ), moyenne=Avg(champ), nombre=Count('id'))

    # Date du minimum et du maximum (pour afficher "le 03/11 à 14:20")
    date_min = qs.filter(**{champ: stats['min']}).values_list('dt', flat=True).first() if stats['nombre'] else None
    date_max = qs.filter(**{champ: stats['max']}).values_list('dt', flat=True).first() if stats['nombre'] else None

    points = [{'dt': dt, 'v': v} for dt, v in qs.values_list('dt', champ)]

    return Response({
        'champ': champ,
        'periode': periode,
        'stats': {
            'min': stats['min'],
            'max': stats['max'],
            'moyenne': round(stats['moyenne'], 1) if stats['moyenne'] is not None else None,
            'nombre': stats['nombre'],
            'date_min': date_min,
            'date_max': date_max,
        },
        'points': points,
    })
