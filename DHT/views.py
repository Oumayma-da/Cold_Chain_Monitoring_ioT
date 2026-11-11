from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render

from .forms import MesureTestForm, SeuilForm
from .models import Dht11, Seuil

# Infos d'affichage pour chaque type de mesure
MESURES = {
    'temp': {'code': 'temp', 'nom': 'Température', 'unite': '°C'},
    'hum': {'code': 'hum', 'nom': 'Humidité', 'unite': '%'},
}

# B2 : scénarios de test en un clic (les 3 cas du TP + humidité)
SCENARIOS = {
    'normal':   {'nom': 'Normal',            'temp': 20, 'hum': 50, 'etat': 'normal'},
    'limite':   {'nom': 'Limite (25 °C)',    'temp': 25, 'hum': 55, 'etat': 'attention'},
    'alerte':   {'nom': 'Alerte (30 °C)',    'temp': 30, 'hum': 55, 'etat': 'critique'},
    'humidite': {'nom': 'Humidité critique', 'temp': 21, 'hum': 80, 'etat': 'critique'},
}


def config_js():
    """Configuration envoyée au JavaScript (seuils, délais...)."""
    return {
        'seuils': Seuil.tous(),   # lus depuis la base (modifiables par l'admin)
        'horsLigne': settings.CAPTEUR_HORS_LIGNE_SECONDES,
        'rafraichissement': settings.RAFRAICHISSEMENT_SECONDES,
        'mesures': MESURES,
    }


# A1 + A2 : tableau de bord avec les cartes
def dashboard(request):
    return render(request, 'DHT/dashboard.html', {
        'config': config_js(),
        'page': 'dashboard',
    })


# A3 + A4 : page graphique d'une mesure (temp ou hum)
def graphique(request, champ):
    if champ not in MESURES:
        raise Http404("Mesure inconnue")
    return render(request, 'DHT/graphique.html', {
        'config': config_js(),
        'mesure': MESURES[champ],
        'page': champ,
    })


# B2 : insertion de mesures de test (réservé à l'admin)
def enregistrer_mesure(temp, hum, dt=None):
    """Crée une mesure. dt permet de simuler une date passée."""
    mesure = Dht11.objects.create(temp=temp, hum=hum)
    if dt:
        # dt est rempli automatiquement (auto_now_add) -> on le corrige après
        Dht11.objects.filter(pk=mesure.pk).update(dt=dt)
        mesure.refresh_from_db()
    # (Étape C : c'est ici qu'on appellera la vérification des alertes)
    return mesure


@staff_member_required
def inserer_test(request):
    form = MesureTestForm()

    if request.method == 'POST':
        scenario = request.POST.get('scenario')

        if scenario in SCENARIOS:
            # Bouton de scénario rapide
            s = SCENARIOS[scenario]
            mesure = enregistrer_mesure(s['temp'], s['hum'])
            messages.success(request, f"Scénario « {s['nom']} » inséré : {mesure.temp} °C / {mesure.hum} %")
            return redirect('inserer_test')

        # Formulaire manuel
        form = MesureTestForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            mesure = enregistrer_mesure(d['temp'], d['hum'], d['dt'])
            messages.success(request, f"Mesure insérée : {mesure.temp} °C / {mesure.hum} %")
            return redirect('inserer_test')

    dernieres = Dht11.objects.filter(dt__isnull=False).order_by('-dt', '-id')[:10]

    return render(request, 'DHT/inserer.html', {
        'config': config_js(),
        'page': 'inserer',
        'form': form,
        'scenarios': SCENARIOS,
        'dernieres': dernieres,
    })


# Page Seuils : l'admin modifie les seuils de chaque mesure
@staff_member_required
def modifier_seuils(request):
    seuil_temp = Seuil.obtenir('temp')
    seuil_hum = Seuil.obtenir('hum')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Bouton "Rétablir les valeurs par défaut" (celles de settings.py)
        if action in ('defaut_temp', 'defaut_hum'):
            champ = action.replace('defaut_', '')
            Seuil.objects.filter(champ=champ).update(**settings.SEUILS[champ])
            messages.success(request, f"Seuils {MESURES[champ]['nom']} remis aux valeurs par défaut.")
            return redirect('modifier_seuils')

        # Bouton "Enregistrer" d'une des deux cartes
        form_temp = SeuilForm(request.POST if action == 'temp' else None, instance=seuil_temp, prefix='temp')
        form_hum = SeuilForm(request.POST if action == 'hum' else None, instance=seuil_hum, prefix='hum')
        form = form_temp if action == 'temp' else form_hum

        if action in ('temp', 'hum') and form.is_valid():
            form.save()
            messages.success(request, f"Seuils {MESURES[action]['nom']} enregistrés.")
            return redirect('modifier_seuils')
    else:
        form_temp = SeuilForm(instance=seuil_temp, prefix='temp')
        form_hum = SeuilForm(instance=seuil_hum, prefix='hum')

    return render(request, 'DHT/seuils.html', {
        'config': config_js(),
        'page': 'seuils',
        'cartes': [
            {'mesure': MESURES['temp'], 'form': form_temp, 'seuil': seuil_temp},
            {'mesure': MESURES['hum'], 'form': form_hum, 'seuil': seuil_hum},
        ],
    })
