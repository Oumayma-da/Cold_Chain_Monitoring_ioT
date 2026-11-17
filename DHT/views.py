from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ClotureForm, CommentaireForm, MesureTestForm, SeuilForm
from .incidents import construire_chronologie, resume_operateurs, traiter_mesure
from .pdf import fiche_incident_pdf
from .models import Dht11, Evenement, Incident, Operateur, Seuil

# ---------------------------------------------------------
# Informations d'affichage pour chaque type de mesure
# ---------------------------------------------------------
MESURES = {
    'temp': {'code': 'temp', 'nom': 'Température', 'unite': '°C'},
    'hum': {'code': 'hum', 'nom': 'Humidité', 'unite': '%'},
}


# B2 : scénarios de test en un clic, calculés à partir des seuils actuels
def scenarios():
    s = Seuil.tous()
    t, h = s['temp'], s['hum']
    temp_ok = round((t['min'] + t['max']) / 2, 1)   # milieu de la plage
    hum_ok = round((h['min'] + h['max']) / 2, 1)
    return {
        'normal': {'nom': 'Normal',              'temp': temp_ok,      'hum': hum_ok, 'etat': 'normal'},
        'chaud':  {'nom': 'Trop chaud',          'temp': t['max'] + 3, 'hum': hum_ok, 'etat': 'critique'},
        'froid':  {'nom': 'Trop froid',          'temp': t['min'] - 2, 'hum': hum_ok, 'etat': 'critique'},
        'humide': {'nom': 'Humidité trop haute', 'temp': temp_ok,      'hum': min(100, h['max'] + 10), 'etat': 'critique'},
    }


# ---------------------------------------------------------
# Configuration envoyée au JavaScript
# ---------------------------------------------------------
def config_js():
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
# Enregistrer une mesure (page de test) + gérer l'incident
# ---------------------------------------------------------
def enregistrer_mesure(temp, hum, dt=None):
    """Enregistre une mesure, puis applique la logique des incidents."""
    mesure = Dht11.objects.create(temp=temp, hum=hum)

    # Date personnalisée (pour simuler le passé)
    if dt:
        Dht11.objects.filter(pk=mesure.pk).update(dt=dt)
        mesure.refresh_from_db()

    # Ouvrir / mettre à jour / fermer l'incident + envoyer les alertes
    traiter_mesure(mesure)
    return mesure


# ---------------------------------------------------------
# B2 : Page d'insertion des mesures de test (admin)
# ---------------------------------------------------------
@staff_member_required
def inserer_test(request):
    form = MesureTestForm()

    if request.method == 'POST':
        scenario = request.POST.get('scenario')
        liste = scenarios()

        if scenario in liste:
            s = liste[scenario]
            mesure = enregistrer_mesure(s['temp'], s['hum'])
            messages.success(request, f"Scénario « {s['nom']} » inséré : {mesure.temp} °C / {mesure.hum} %")
            return redirect('inserer_test')

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
        'scenarios': scenarios(),
        'dernieres': dernieres,
    })


# ---------------------------------------------------------
# Page Seuils (admin)
# ---------------------------------------------------------
@staff_member_required
def modifier_seuils(request):
    seuil_temp = Seuil.obtenir('temp')
    seuil_hum = Seuil.obtenir('hum')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Rétablir les valeurs par défaut (celles de settings.py)
        if action in ('defaut_temp', 'defaut_hum'):
            champ = action.replace('defaut_', '')
            defaut = settings.SEUILS[champ]
            Seuil.objects.filter(champ=champ).update(valeur_min=defaut['min'], valeur_max=defaut['max'])
            messages.success(request, f"Seuils {MESURES[champ]['nom']} remis aux valeurs par défaut.")
            return redirect('modifier_seuils')

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


# =========================================================
#  NOUVEAU : INCIDENTS
# =========================================================
FILTRES_INCIDENTS = {
    'tous': ('Tous', None),
    'en_cours': ('En cours', Incident.OUVERT),
    'resolus': ('Résolus', Incident.RESOLU),
    'clotures': ('Clôturés', Incident.CLOTURE),
}


@login_required
def liste_incidents(request):
    filtre = request.GET.get('filtre', 'tous')
    if filtre not in FILTRES_INCIDENTS:
        filtre = 'tous'

    incidents = Incident.objects.annotate(
        nb_accuses=Count('evenements', filter=Q(evenements__type=Evenement.ACCUSE)),
        nb_commentaires=Count('evenements', filter=Q(evenements__type=Evenement.COMMENTAIRE)),
    )
    statut = FILTRES_INCIDENTS[filtre][1]
    if statut:
        incidents = incidents.filter(statut=statut)

    return render(request, 'DHT/incidents.html', {
        'config': config_js(),
        'page': 'incidents',
        'incidents': incidents,
        'filtre': filtre,
        'filtres': [(code, nom) for code, (nom, _) in FILTRES_INCIDENTS.items()],
        'nb_operateurs': Operateur.objects.count(),
    })


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    operateur = getattr(request.user, 'operateur', None)   # None si c'est l'admin
    form_commentaire = CommentaireForm()
    form_cloture = ClotureForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- 1. Accusé de réception (opérateur, une seule fois) ---
        if action == 'accuse' and operateur:
            deja = incident.evenements.filter(type=Evenement.ACCUSE, operateur=operateur).exists()
            if not deja:
                Evenement.objects.create(
                    incident=incident, type=Evenement.ACCUSE, auteur=request.user, operateur=operateur,
                    message=f"{operateur} a accusé réception de l'incident",
                )
                messages.success(request, "Accusé de réception enregistré.")
            return redirect('incident_detail', pk=pk)

        # --- 2. Commentaire (opérateurs + admin) ---
        if action == 'commenter':
            form_commentaire = CommentaireForm(request.POST)
            if form_commentaire.is_valid():
                Evenement.objects.create(
                    incident=incident, type=Evenement.COMMENTAIRE, auteur=request.user, operateur=operateur,
                    message=form_commentaire.cleaned_data['texte'],
                )
                messages.success(request, "Commentaire ajouté.")
                return redirect('incident_detail', pk=pk)

        # --- 3. Clôture (admin seulement) ---
        if action == 'cloturer' and request.user.is_staff and incident.statut != Incident.CLOTURE:
            form_cloture = ClotureForm(request.POST)
            if form_cloture.is_valid():
                maintenant = timezone.now()
                incident.statut = Incident.CLOTURE
                incident.cloture_le = maintenant
                if incident.fin is None:
                    incident.fin = maintenant
                incident.save()
                Evenement.objects.create(
                    incident=incident, type=Evenement.CLOTURE, auteur=request.user,
                    message=f"Incident clôturé par {request.user.username} : {form_cloture.cleaned_data['raison']}",
                )
                messages.success(request, "Incident clôturé.")
                return redirect('incident_detail', pk=pk)

    # --- Tableau des opérateurs + chronologie (fonctions dans incidents.py) ---
    lignes_operateurs = resume_operateurs(incident)

    deja_accuse = bool(operateur) and incident.evenements.filter(type=Evenement.ACCUSE, operateur=operateur).exists()

    return render(request, 'DHT/incident_detail.html', {
        'config': config_js(),
        'page': 'incidents',
        'incident': incident,
        'operateur': operateur,
        'deja_accuse': deja_accuse,
        'lignes_operateurs': lignes_operateurs,
        'commentaires': incident.evenements.filter(type=Evenement.COMMENTAIRE).select_related('auteur', 'operateur'),
        'chronologie': construire_chronologie(incident),
        'form_commentaire': form_commentaire,
        'form_cloture': form_cloture,
    })


@staff_member_required
def export_fiche_pdf(request, pk):
    """Fiche d'incident complète en PDF (à imprimer / archiver / signer) — réservée à l'admin."""
    incident = get_object_or_404(Incident, pk=pk)
    pdf = fiche_incident_pdf(incident, request.user)

    reponse = HttpResponse(pdf, content_type='application/pdf')
    # "inline" : s'ouvre dans le navigateur (on peut ensuite l'enregistrer ou l'imprimer)
    reponse['Content-Disposition'] = f'inline; filename="fiche_incident_{incident.pk}.pdf"'
    return reponse
