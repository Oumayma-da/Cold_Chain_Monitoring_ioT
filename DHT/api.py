import csv
import logging
from datetime import timedelta

from django.db.models import Avg, Count, Max, Min
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .incidents import incident_en_cours, traiter_mesure
from .models import Dht11, Seuil
from .serializers import DHT11serialize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# API 1 : Récupérer toutes les mesures
# ---------------------------------------------------------
@api_view(['GET'])
def Dlist(request):
    all_data = Dht11.objects.all()
    data = DHT11serialize(all_data, many=True).data
    return Response({'data': data})


# ---------------------------------------------------------
# API 2 : L'ESP envoie une mesure -> on l'enregistre puis on gère l'incident
# POST /api/post   {"temp": 5.2, "hum": 45}
# ---------------------------------------------------------
class Dhtviews(generics.CreateAPIView):
    queryset = Dht11.objects.all()
    serializer_class = DHT11serialize

    def perform_create(self, serializer):
        # 1. Enregistrer la mesure
        mesure = serializer.save()

        # 2. Ouvrir / mettre à jour / fermer l'incident + alertes
        #    (si ça plante, la mesure reste enregistrée et l'ESP reçoit quand même "201 OK")
        try:
            traiter_mesure(mesure)
        except Exception:
            logger.exception("Erreur pendant le traitement de l'incident")


# ---------------------------------------------------------
# API 3 : Dernière mesure valide + incident en cours
# GET /api/derniere/
# ---------------------------------------------------------
@api_view(['GET'])
def derniere_mesure(request):
    mesure = (
        Dht11.objects
        .filter(temp__isnull=False, hum__isnull=False, dt__isnull=False)
        .order_by('-dt', '-id')
        .first()
    )

    incident = incident_en_cours()
    infos_incident = None
    if incident:
        infos_incident = {
            'id': incident.pk,
            'debut': incident.debut,
            'compteur': incident.compteur,
            'niveau': incident.niveau_atteint,
            'duree': incident.duree_texte,
        }

    if mesure is None:
        return Response({'mesure': None, 'seuils': Seuil.tous(), 'incident': infos_incident})

    return Response({
        'mesure': {
            'temp': mesure.temp,
            'hum': mesure.hum,
            'dt': mesure.dt,
        },
        'serveur_maintenant': timezone.now(),
        'seuils': Seuil.tous(),
        'incident': infos_incident,
    })


# ---------------------------------------------------------
# Filtre commun (graphiques + export CSV)
# periode : 1h | 24h | 7j | 30j | tout   ou   debut / fin (AAAA-MM-JJ)
# ---------------------------------------------------------
PERIODES = {
    '1h': timedelta(hours=1),
    '24h': timedelta(hours=24),
    '7j': timedelta(days=7),
    '30j': timedelta(days=30),
}


def filtrer_mesures(request, qs):
    """Applique le filtre de période / dates. Renvoie (queryset, nom_de_la_periode)."""
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
        qs = qs.filter(dt__gte=timezone.now() - PERIODES[periode])
    else:
        periode = 'tout'

    return qs.order_by('dt', 'id'), periode


# ---------------------------------------------------------
# API 4 : Mesures filtrées + statistiques (graphiques)
# GET /api/mesures/?champ=temp&periode=24h
# ---------------------------------------------------------
@api_view(['GET'])
def mesures(request):
    champ = request.GET.get('champ')
    if champ not in ('temp', 'hum'):
        return Response(
            {'erreur': "Le paramètre champ doit être 'temp' ou 'hum'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = Dht11.objects.filter(dt__isnull=False, **{f'{champ}__isnull': False})
    qs, periode = filtrer_mesures(request, qs)

    stats = qs.aggregate(min=Min(champ), max=Max(champ), moyenne=Avg(champ), nombre=Count('id'))

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


# ---------------------------------------------------------
# NOUVEAU : Export CSV des mesures (même filtre que le graphique)
# GET /export/mesures.csv?periode=7j
# ---------------------------------------------------------
def nombre_fr(valeur):
    """24.5 -> "24,5" (Excel en français attend une virgule)."""
    return '' if valeur is None else str(valeur).replace('.', ',')


def export_mesures_csv(request):
    qs = Dht11.objects.filter(dt__isnull=False)
    qs, periode = filtrer_mesures(request, qs)

    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    nom = f"mesures_{periode}_{timezone.localtime():%Y-%m-%d_%H%M}.csv"
    reponse['Content-Disposition'] = f'attachment; filename="{nom}"'
    reponse.write('﻿')  # BOM : pour qu'Excel lise bien les accents

    ecrivain = csv.writer(reponse, delimiter=';')
    ecrivain.writerow(['Date', 'Heure', 'Température (°C)', 'Humidité (%)'])
    for m in qs:
        dt = timezone.localtime(m.dt)
        ecrivain.writerow([dt.strftime('%d/%m/%Y'), dt.strftime('%H:%M:%S'), nombre_fr(m.temp), nombre_fr(m.hum)])
    return reponse
