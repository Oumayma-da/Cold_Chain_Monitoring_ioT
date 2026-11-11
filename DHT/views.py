
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render

from .forms import MesureTestForm, SeuilForm
from .models import Dht11, Seuil
from .notifications import verifier_alertes


# ---------------------------------------------------------
# Informations d'affichage pour chaque type de mesure
# ---------------------------------------------------------
MESURES = {
    'temp': {
        'code': 'temp',
        'nom': 'Température',
        'unite': '°C'
    },
    'hum': {
        'code': 'hum',
        'nom': 'Humidité',
        'unite': '%'
    },
}


# ---------------------------------------------------------
# Scénarios de test en un clic
# ---------------------------------------------------------
SCENARIOS = {
    'normal': {
        'nom': 'Normal',
        'temp': 20,
        'hum': 50,
        'etat': 'normal'
    },
    'limite': {
        'nom': 'Limite (25 °C)',
        'temp': 25,
        'hum': 55,
        'etat': 'attention'
    },
    'alerte': {
        'nom': 'Alerte (30 °C)',
        'temp': 30,
        'hum': 55,
        'etat': 'critique'
    },
    'humidite': {
        'nom': 'Humidité critique',
        'temp': 21,
        'hum': 80,
        'etat': 'critique'
    },
}


# ---------------------------------------------------------
# Configuration envoyée au JavaScript
# ---------------------------------------------------------
def config_js():
    """Configuration des seuils, délais et mesures."""

    return {
        'seuils': Seuil.tous(),
        'horsLigne': settings.CAPTEUR_HORS_LIGNE_SECONDES,
        'rafraichissement': settings.RAFRAICHISSEMENT_SECONDES,
        'mesures': MESURES,
    }


# ---------------------------------------------------------
# A1 + A2 : Tableau de bord
# ---------------------------------------------------------
def dashboard(request):

    return render(request, 'DHT/dashboard.html', {
        'config': config_js(),
        'page': 'dashboard',
    })


# ---------------------------------------------------------
# A3 + A4 : Graphiques des mesures
# ---------------------------------------------------------
def graphique(request, champ):

    if champ not in MESURES:
        raise Http404("Mesure inconnue")

    return render(request, 'DHT/graphique.html', {
        'config': config_js(),
        'mesure': MESURES[champ],
        'page': champ,
    })


# ---------------------------------------------------------
# B2 + Alertes : Enregistrer une nouvelle mesure
# ---------------------------------------------------------
def enregistrer_mesure(temp, hum, dt=None):
    """
    Enregistre une mesure dans SQLite.

    Si la température dépasse 25 °C,
    envoie automatiquement une alerte Gmail et Telegram.
    """

    # 1. Enregistrer la mesure dans la base de données
    mesure = Dht11.objects.create(
        temp=temp,
        hum=hum
    )

    # 2. Corriger la date si une date personnalisée est fournie
    if dt:
        Dht11.objects.filter(
            pk=mesure.pk
        ).update(dt=dt)

        mesure.refresh_from_db()

    # 3. Vérifier la température et envoyer les alertes
    verifier_alertes(mesure.temp)

    # 4. Retourner la mesure enregistrée
    return mesure


# ---------------------------------------------------------
# B2 : Page d'insertion des mesures de test
# Réservée aux administrateurs
# ---------------------------------------------------------
@staff_member_required
def inserer_test(request):

    form = MesureTestForm()

    if request.method == 'POST':

        scenario = request.POST.get('scenario')

        # -------------------------------------------------
        # Cas 1 : Scénario rapide
        # -------------------------------------------------
        if scenario in SCENARIOS:

            s = SCENARIOS[scenario]

            # Enregistrer la mesure + vérifier les alertes
            mesure = enregistrer_mesure(
                s['temp'],
                s['hum']
            )

            messages.success(
                request,
                f"Scénario « {s['nom']} » inséré : "
                f"{mesure.temp} °C / {mesure.hum} %"
            )

            return redirect('inserer_test')

        # -------------------------------------------------
        # Cas 2 : Insertion manuelle
        # -------------------------------------------------
        form = MesureTestForm(request.POST)

        if form.is_valid():

            d = form.cleaned_data

            # Enregistrer la mesure + vérifier les alertes
            mesure = enregistrer_mesure(
                d['temp'],
                d['hum'],
                d['dt']
            )

            messages.success(
                request,
                f"Mesure insérée : "
                f"{mesure.temp} °C / {mesure.hum} %"
            )

            return redirect('inserer_test')

    # -----------------------------------------------------
    # Afficher les 10 dernières mesures
    # -----------------------------------------------------
    dernieres = (
        Dht11.objects
        .filter(dt__isnull=False)
        .order_by('-dt', '-id')[:10]
    )

    return render(request, 'DHT/inserer.html', {
        'config': config_js(),
        'page': 'inserer',
        'form': form,
        'scenarios': SCENARIOS,
        'dernieres': dernieres,
    })


# ---------------------------------------------------------
# Page Seuils : Modifier les seuils
# ---------------------------------------------------------
@staff_member_required
def modifier_seuils(request):

    seuil_temp = Seuil.obtenir('temp')
    seuil_hum = Seuil.obtenir('hum')

    if request.method == 'POST':

        action = request.POST.get('action')

        # -------------------------------------------------
        # Rétablir les valeurs par défaut
        # -------------------------------------------------
        if action in ('defaut_temp', 'defaut_hum'):

            champ = action.replace('defaut_', '')

            Seuil.objects.filter(
                champ=champ
            ).update(**settings.SEUILS[champ])

            messages.success(
                request,
                f"Seuils {MESURES[champ]['nom']} "
                f"remis aux valeurs par défaut."
            )

            return redirect('modifier_seuils')

        # -------------------------------------------------
        # Formulaires de modification
        # -------------------------------------------------
        form_temp = SeuilForm(
            request.POST if action == 'temp' else None,
            instance=seuil_temp,
            prefix='temp'
        )

        form_hum = SeuilForm(
            request.POST if action == 'hum' else None,
            instance=seuil_hum,
            prefix='hum'
        )

        form = (
            form_temp
            if action == 'temp'
            else form_hum
        )

        if action in ('temp', 'hum') and form.is_valid():

            form.save()

            messages.success(
                request,
                f"Seuils {MESURES[action]['nom']} enregistrés."
            )

            return redirect('modifier_seuils')

    else:

        form_temp = SeuilForm(
            instance=seuil_temp,
            prefix='temp'
        )

        form_hum = SeuilForm(
            instance=seuil_hum,
            prefix='hum'
        )

    return render(request, 'DHT/seuils.html', {
        'config': config_js(),
        'page': 'seuils',
        'cartes': [
            {
                'mesure': MESURES['temp'],
                'form': form_temp,
                'seuil': seuil_temp
            },
            {
                'mesure': MESURES['hum'],
                'form': form_hum,
                'seuil': seuil_hum
            },
        ],
    })
