"""
Logique des incidents (celle du tableau au tableau blanc).

À chaque nouvelle mesure de température :

    si temp < TEMP_MIN ou temp > TEMP_MAX :  incident = 1
    sinon                                  :  incident = 0

    si incident = 1 : compteur = compteur + 1   (dans le MÊME incident)
    sinon           : compteur = 0              (l'incident se termine)

Escalade (settings.ESCALADE) : Opérateur 1 alerté dès compteur = 1,
Opérateur 2 dès compteur = 4, Opérateur 3 dès compteur = 7.
"""
from django.conf import settings
from django.db import transaction
from django.urls import reverse

from .models import Evenement, Incident, Operateur, Seuil
from .notifications import notifier_operateur


def incident_en_cours():
    """L'incident ouvert (il y en a au maximum un à la fois), ou None."""
    return Incident.objects.filter(statut=Incident.OUVERT).order_by('-debut').first()


def operateurs_a_alerter(compteur):
    """Liste des opérateurs à alerter pour ce compteur (selon settings.ESCALADE)."""
    niveaux = [niveau for niveau, a_partir_de in settings.ESCALADE.items() if compteur >= a_partir_de]
    return list(Operateur.objects.filter(niveau__in=niveaux).select_related('user'))


def lien_incident(incident):
    return settings.SITE_URL.rstrip('/') + reverse('incident_detail', args=[incident.pk])


@transaction.atomic
def traiter_mesure(mesure):
    """Appelée à chaque nouvelle mesure (API de l'ESP + page de test)."""
    temp = mesure.temp
    if temp is None:
        return None

    seuil = Seuil.obtenir('temp')
    hors_limites = temp < seuil.valeur_min or temp > seuil.valeur_max
    incident = incident_en_cours()

    # ------------------------------------------------------
    # Cas 1 : température normale
    # ------------------------------------------------------
    if not hors_limites:
        if incident:
            terminer_incident(incident, mesure, seuil)
        return incident

    # ------------------------------------------------------
    # Cas 2 : température hors limites
    # ------------------------------------------------------
    if incident is None:
        incident = Incident.objects.create(
            debut=mesure.dt,
            seuil_min=seuil.valeur_min,
            seuil_max=seuil.valeur_max,
            temp_max=temp,
            temp_min=temp,
        )
        Evenement.objects.create(
            incident=incident, date=mesure.dt, type=Evenement.OUVERTURE, valeur=temp,
            message=f"Incident ouvert : {temp} °C (plage autorisée {seuil.valeur_min} à {seuil.valeur_max} °C)",
        )

    # Compteur + valeurs extrêmes
    incident.compteur += 1
    incident.temp_max = max(incident.temp_max, temp)
    incident.temp_min = min(incident.temp_min, temp)

    Evenement.objects.create(
        incident=incident, date=mesure.dt, type=Evenement.MESURE, valeur=temp,
        message=f"Mesure hors limites n°{incident.compteur} : {temp} °C",
    )

    # Escalade : un nouveau niveau est-il atteint ?
    destinataires = operateurs_a_alerter(incident.compteur)
    niveau = max([n for n, a_partir_de in settings.ESCALADE.items() if incident.compteur >= a_partir_de], default=0)
    if niveau > incident.niveau_atteint:
        incident.niveau_atteint = niveau
        if niveau > 1:
            Evenement.objects.create(
                incident=incident, date=mesure.dt, type=Evenement.ESCALADE,
                message=f"Escalade : l'Opérateur {niveau} est maintenant alerté "
                        f"({incident.compteur} mesures hors limites de suite)",
            )
    incident.save()

    # Envoi des alertes (Gmail + Telegram) à chaque opérateur concerné
    if not destinataires:
        Evenement.objects.create(
            incident=incident, date=mesure.dt, type=Evenement.ALERTE,
            message="Aucun opérateur enregistré pour ce niveau : alerte non envoyée",
        )
    for operateur in destinataires:
        sujet, texte = message_alerte(incident, operateur, temp, seuil)
        resultat = notifier_operateur(operateur, sujet, texte)
        Evenement.objects.create(
            incident=incident, date=mesure.dt, type=Evenement.ALERTE, operateur=operateur,
            message=f"Alerte pour {operateur} : {resultat}",
        )
    return incident


def terminer_incident(incident, mesure, seuil):
    """La température est revenue dans la plage : l'incident est résolu."""
    incident.statut = Incident.RESOLU
    incident.fin = mesure.dt
    incident.save()

    Evenement.objects.create(
        incident=incident, date=mesure.dt, type=Evenement.RESOLUTION, valeur=mesure.temp,
        message=f"Température revenue à {mesure.temp} °C (dans la plage {seuil.valeur_min} à "
                f"{seuil.valeur_max} °C). Incident résolu après {incident.duree_texte}.",
    )

    # On prévient les opérateurs qui avaient été alertés
    for operateur in operateurs_a_alerter(incident.compteur):
        sujet = f"[RÉSOLU] Incident #{incident.pk} — température revenue à {mesure.temp} °C"
        texte = (
            f"Bonjour {operateur.get_niveau_display()},\n\n"
            f"✅ L'incident #{incident.pk} est RÉSOLU.\n"
            f"Température revenue à {mesure.temp} °C (plage autorisée {seuil.valeur_min} à {seuil.valeur_max} °C).\n"
            f"Durée de l'incident : {incident.duree_texte} — {incident.compteur} mesure(s) hors limites.\n\n"
            f"Détail de l'incident : {lien_incident(incident)}"
        )
        resultat = notifier_operateur(operateur, sujet, texte)
        Evenement.objects.create(
            incident=incident, date=mesure.dt, type=Evenement.ALERTE, operateur=operateur,
            message=f"Fin d'incident signalée à {operateur} : {resultat}",
        )


def message_alerte(incident, operateur, temp, seuil):
    """Sujet + texte de l'alerte, adaptés à l'opérateur (son niveau, l'escalade)."""
    premiere_fois = incident.compteur == settings.ESCALADE.get(operateur.niveau)
    if operateur.niveau == 1:
        role = "Tu es le 1er responsable : vérifie le réfrigérateur."
    else:
        role = (f"Escalade niveau {operateur.niveau} : l'incident dure depuis "
                f"{incident.compteur} mesures sans retour à la normale.")
    sens = "trop élevée" if temp > seuil.valeur_max else "trop basse"

    sujet = f"[ALERTE] Incident #{incident.pk} — {temp} °C ({sens})"
    if premiere_fois and operateur.niveau > 1:
        sujet = f"[ESCALADE] Incident #{incident.pk} — Opérateur {operateur.niveau} alerté — {temp} °C"

    texte = (
        f"Bonjour {operateur.get_niveau_display()},\n\n"
        f"⚠ ALERTE CHAÎNE DU FROID — Incident #{incident.pk}\n"
        f"Température : {temp} °C ({sens}) — plage autorisée {seuil.valeur_min} à {seuil.valeur_max} °C\n"
        f"Mesure hors limites n°{incident.compteur} — incident ouvert depuis {incident.duree_texte}\n\n"
        f"{role}\n\n"
        f"👉 Ouvre l'incident et clique sur « J'ai vu l'incident » pour accuser réception :\n"
        f"{lien_incident(incident)}"
    )
    return sujet, texte


# =========================================================
#  AFFICHAGE : résumé des opérateurs + chronologie
#  (utilisés par la page détail ET par la fiche PDF)
# =========================================================
def formater_delai(minutes):
    minutes = max(int(minutes), 0)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def resume_operateurs(incident):
    """Pour chaque opérateur : 1re alerte, accusé de réception, délai, dernier commentaire."""
    lignes = []
    for op in Operateur.objects.select_related('user'):
        premiere_alerte = incident.evenements.filter(type=Evenement.ALERTE, operateur=op).first()
        accuse = incident.evenements.filter(type=Evenement.ACCUSE, operateur=op).first()
        dernier_commentaire = incident.evenements.filter(type=Evenement.COMMENTAIRE, operateur=op).last()
        delai = None
        if premiere_alerte and accuse:
            delai = formater_delai((accuse.date - premiere_alerte.date).total_seconds() // 60)
        lignes.append({
            'operateur': op,
            'alerte_a_partir_de': settings.ESCALADE.get(op.niveau),
            'premiere_alerte': premiere_alerte,
            'accuse': accuse,
            'delai': delai,
            'dernier_commentaire': dernier_commentaire,
        })
    return lignes


# Catégorie de chaque ligne (sert aux couleurs et aux filtres)
CATEGORIES = {
    Evenement.OUVERTURE: 'etape',
    Evenement.MESURE: 'mesure',
    Evenement.ESCALADE: 'etape',
    Evenement.ACCUSE: 'operateur',
    Evenement.COMMENTAIRE: 'operateur',
    Evenement.RESOLUTION: 'etape',
    Evenement.CLOTURE: 'etape',
}

TITRES = {
    Evenement.OUVERTURE: "Ouverture de l'incident",
    Evenement.MESURE: "Mesure hors limites",
    Evenement.ESCALADE: "Escalade",
    Evenement.ACCUSE: "Accusé de réception",
    Evenement.COMMENTAIRE: "Commentaire",
    Evenement.RESOLUTION: "Retour à la normale",
    Evenement.CLOTURE: "Clôture du dossier",
}


def nom_auteur(evenement):
    if evenement.operateur and evenement.type in (Evenement.ACCUSE, Evenement.COMMENTAIRE):
        return evenement.operateur.get_niveau_display()
    if evenement.auteur:
        return f"{evenement.auteur.username} (admin)" if evenement.auteur.is_staff else evenement.auteur.username
    return "Système"


def construire_chronologie(incident):
    """
    Regroupe le journal brut en lignes lisibles :
      - l'ouverture + la 1re mesure = 1 ligne
      - une mesure + ses alertes (+ escalade éventuelle) = 1 ligne
      - le retour à la normale + les opérateurs informés = 1 ligne
    """
    lignes = []
    for e in incident.evenements.select_related('auteur', 'operateur'):
        derniere = lignes[-1] if lignes else None

        # Alerte -> ajoutée à la ligne précédente (mesure ou retour à la normale)
        if e.type == Evenement.ALERTE:
            if derniere:
                if e.operateur:
                    derniere['operateurs'].append(f"Op{e.operateur.niveau}")
                else:
                    derniere['note'] = "Aucun opérateur enregistré : alerte non envoyée"
            continue

        # Escalade -> étiquette sur la ligne de la mesure
        if e.type == Evenement.ESCALADE:
            if derniere:
                niveau = e.message.split("l'Opérateur ")[1][0] if "l'Opérateur " in e.message else '?'
                derniere['escalade'] = f"Escalade : Opérateur {niveau}"
                derniere['categorie'] = 'escalade'
            continue

        # 1re mesure -> fusionnée avec l'ouverture
        if e.type == Evenement.MESURE and derniere and derniere['type'] == Evenement.OUVERTURE and not derniere['operateurs']:
            derniere['detail'] = (f"Mesure n°1 : {e.valeur} °C, hors de la plage autorisée "
                                  f"({incident.seuil_min} à {incident.seuil_max} °C)")
            continue

        if e.type == Evenement.MESURE:
            detail = f"Mesure n°{incident_compteur_depuis(e)} : {e.valeur} °C"
            par = "Capteur"
        elif e.type == Evenement.OUVERTURE:
            detail = e.message
            par = "Capteur"
        elif e.type == Evenement.ACCUSE:
            detail = "A confirmé avoir vu l'incident"
            par = nom_auteur(e)
        elif e.type == Evenement.RESOLUTION:
            detail = e.message
            par = "Capteur"
        elif e.type == Evenement.CLOTURE:
            detail = e.message.split(' : ', 1)[1] if ' : ' in e.message else e.message
            par = nom_auteur(e)
        else:
            detail = e.message
            par = nom_auteur(e)

        lignes.append({
            'date': e.date,
            'type': e.type,
            'categorie': CATEGORIES.get(e.type, 'etape'),
            'titre': TITRES.get(e.type, e.get_type_display()),
            'detail': detail,
            'valeur': e.valeur,
            'par': par,
            'operateurs': [],
            'escalade': '',
            'note': '',
        })
    return lignes


def incident_compteur_depuis(evenement):
    """Le numéro de la mesure est écrit dans le message : "Mesure hors limites n°4 : 9.2 °C"."""
    try:
        return evenement.message.split('n°')[1].split(' ')[0]
    except IndexError:
        return '?'
