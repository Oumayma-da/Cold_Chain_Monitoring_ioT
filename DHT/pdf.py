"""
Fiche d'incident en PDF (bibliothèque ReportLab).

Structure de la fiche :
    En-tête   : titre, n° d'incident, état
    1. Informations générales
    2. Opérateurs et accusés de réception
    3. Chronologie de l'incident (journal regroupé)
    4. Discussion
    5. Clôture et validation (cases de signature)
    Pied de page : date d'édition + "Page X / Y"
"""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .incidents import construire_chronologie, resume_operateurs
from .models import Evenement, Incident

# ---------------------------------------------------------
# Couleurs
# ---------------------------------------------------------
NOIR = colors.HexColor('#14161c')
GRIS = colors.HexColor('#5b5f6b')
GRIS_CLAIR = colors.HexColor('#8b8f9a')
BORDURE = colors.HexColor('#d9dce3')
FOND = colors.HexColor('#f3f4f7')
ROUGE = colors.HexColor('#a32424')
ROUGE_CLAIR = colors.HexColor('#fbe4e4')
VERT = colors.HexColor('#0a6e0a')
VERT_CLAIR = colors.HexColor('#e3f5e3')
ORANGE_CLAIR = colors.HexColor('#fdebd8')
VIOLET_CLAIR = colors.HexColor('#efeafa')

COULEURS_ETAT = {
    Incident.OUVERT: (ROUGE_CLAIR, ROUGE),
    Incident.RESOLU: (VERT_CLAIR, VERT),
    Incident.CLOTURE: (FOND, NOIR),
}

# ---------------------------------------------------------
# Styles de texte
# ---------------------------------------------------------
STYLE = ParagraphStyle('normal', fontName='Helvetica', fontSize=9, leading=12, textColor=NOIR)
STYLE_PETIT = ParagraphStyle('petit', parent=STYLE, fontSize=8, leading=10, textColor=GRIS)
STYLE_GRAS = ParagraphStyle('gras', parent=STYLE, fontName='Helvetica-Bold')
STYLE_ENTETE = ParagraphStyle('entete', parent=STYLE, fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)
STYLE_SECTION = ParagraphStyle('section', parent=STYLE, fontName='Helvetica-Bold', fontSize=11.5, leading=14)
STYLE_LABEL = ParagraphStyle('label', parent=STYLE, fontSize=8, textColor=GRIS)
STYLE_VALEUR = ParagraphStyle('valeur', parent=STYLE, fontName='Helvetica-Bold', fontSize=10)


def texte(valeur):
    """Nettoie un texte pour le PDF : caractères spéciaux HTML + caractères non imprimables (émojis...)."""
    if valeur is None:
        return '—'
    valeur = str(valeur).replace('✓', 'OK').replace('✗', 'échec').replace('⚠', '').replace('→', '->')
    valeur = ''.join(c for c in valeur if _imprimable(c))
    return escape(valeur).replace('\n', '<br/>')


def _imprimable(caractere):
    try:
        caractere.encode('cp1252')   # les polices standard du PDF utilisent cet encodage
        return True
    except UnicodeEncodeError:
        return False


def p(valeur, style=STYLE):
    return Paragraph(texte(valeur), style)


def date_fr(dt, secondes=False):
    if not dt:
        return '—'
    return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M:%S' if secondes else '%d/%m/%Y %H:%M')


def titre_section(numero, titre):
    """Titre de section avec une barre de couleur à gauche."""
    t = Table([[Paragraph(f"{numero}. {escape(titre)}", STYLE_SECTION)]], colWidths=[174 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), FOND),
        ('LINEBEFORE', (0, 0), (0, -1), 3, NOIR),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def style_tableau(nb_lignes, alterner=True):
    """Style commun : en-tête foncé, lignes fines, lignes alternées."""
    regles = [
        ('BACKGROUND', (0, 0), (-1, 0), NOIR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, BORDURE),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDURE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]
    if alterner:
        for i in range(2, nb_lignes, 2):
            regles.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fafbfc')))
    return regles


# ---------------------------------------------------------
# Pied de page "Page X / Y" (il faut connaître le nombre total de pages)
# ---------------------------------------------------------
class CanvasNumerote(rl_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self.infos_pied = kwargs.pop('infos_pied', '')
        super().__init__(*args, **kwargs)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for page in self._pages:
            self.__dict__.update(page)
            self._dessiner_pied(total)
            super().showPage()
        super().save()

    def _dessiner_pied(self, total):
        largeur, _ = A4
        self.setStrokeColor(BORDURE)
        self.line(18 * mm, 14 * mm, largeur - 18 * mm, 14 * mm)
        self.setFont('Helvetica', 7.5)
        self.setFillColor(GRIS_CLAIR)
        self.drawString(18 * mm, 9.5 * mm, self.infos_pied)
        self.drawRightString(largeur - 18 * mm, 9.5 * mm, f"Page {self._pageNumber} / {total}")


# ---------------------------------------------------------
# Construction de la fiche
# ---------------------------------------------------------
def fiche_incident_pdf(incident, utilisateur):
    tampon = BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"Fiche incident #{incident.pk}", author="Surveillance IoT",
    )
    elements = []

    # ======================= EN-TÊTE =======================
    fond_etat, encre_etat = COULEURS_ETAT[incident.statut]
    entete = Table([
        [
            Paragraph("<font size=17><b>FICHE D'INCIDENT</b></font><br/>"
                      "<font size=9 color='#5b5f6b'>Chaîne du froid — Surveillance IoT (capteur DHT11)</font>", STYLE),
            Paragraph(f"<font size=17><b>N° {incident.pk}</b></font>",
                      ParagraphStyle('num', parent=STYLE, alignment=TA_RIGHT)),
        ],
    ], colWidths=[124 * mm, 50 * mm])
    entete.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, NOIR),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements += [entete, Spacer(1, 6 * mm)]

    # Bandeau d'état + chiffres clés
    cle = Table([
        [p("État", STYLE_LABEL), p("Début", STYLE_LABEL), p("Fin", STYLE_LABEL),
         p("Durée", STYLE_LABEL), p("Mesures hors limites", STYLE_LABEL)],
        [Paragraph(f"<b>{escape(incident.get_statut_display().upper())}</b>",
                   ParagraphStyle('etat', parent=STYLE, fontSize=11, textColor=encre_etat)),
         p(date_fr(incident.debut), STYLE_VALEUR),
         p(date_fr(incident.fin) if incident.fin else "En cours", STYLE_VALEUR),
         p(incident.duree_texte, STYLE_VALEUR),
         p(incident.compteur, STYLE_VALEUR)],
    ], colWidths=[30 * mm, 37 * mm, 37 * mm, 32 * mm, 38 * mm])
    cle.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BORDURE),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, BORDURE),
        ('BACKGROUND', (0, 0), (0, -1), fond_etat),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
    ]))
    elements += [cle, Spacer(1, 7 * mm)]

    # ======================= 1. INFORMATIONS =======================
    cloture = incident.evenements.filter(type=Evenement.CLOTURE).last()
    infos = [
        ("Température maximale", f"{incident.temp_max} °C", "Température minimale", f"{incident.temp_min} °C"),
        ("Plage autorisée (à l'ouverture)", f"{incident.seuil_min} à {incident.seuil_max} °C",
         "Niveau d'escalade atteint", f"Opérateur {incident.niveau_atteint}"),
        ("Clôturé le", date_fr(incident.cloture_le) if incident.cloture_le else "Non clôturé",
         "Clôturé par", cloture.auteur.username if cloture and cloture.auteur else "—"),
    ]
    tableau_infos = Table(
        [[p(a, STYLE_LABEL), p(b, STYLE_GRAS), p(c, STYLE_LABEL), p(d, STYLE_GRAS)] for a, b, c, d in infos],
        colWidths=[42 * mm, 45 * mm, 42 * mm, 45 * mm],
    )
    tableau_infos.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BORDURE),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, BORDURE),
        ('BACKGROUND', (0, 0), (0, -1), FOND),
        ('BACKGROUND', (2, 0), (2, -1), FOND),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements += [titre_section(1, "Informations générales"), Spacer(1, 3 * mm), tableau_infos, Spacer(1, 7 * mm)]

    # ======================= 2. OPÉRATEURS =======================
    lignes = [[p(x, STYLE_ENTETE) for x in
               ("Opérateur", "Alerté dès", "1re alerte", "Accusé de réception", "Délai de réaction")]]
    for l in resume_operateurs(incident):
        op = l['operateur']
        lignes.append([
            Paragraph(f"<b>{escape(op.get_niveau_display())}</b><br/><font size=7.5 color='#8b8f9a'>"
                      f"{escape(op.user.username)}</font>", STYLE),
            p(f"{l['alerte_a_partir_de']}e mesure"),
            p(date_fr(l['premiere_alerte'].date) if l['premiere_alerte'] else "Pas alerté"),
            p(f"OUI — {date_fr(l['accuse'].date)}" if l['accuse'] else "NON",
              ParagraphStyle('acc', parent=STYLE_GRAS, textColor=VERT if l['accuse'] else ROUGE)),
            p(l['delai'] or '—'),
        ])
    if len(lignes) == 1:
        lignes.append([p("Aucun opérateur enregistré"), '', '', '', ''])
    tableau_ops = Table(lignes, colWidths=[36 * mm, 25 * mm, 34 * mm, 48 * mm, 31 * mm], repeatRows=1)
    tableau_ops.setStyle(TableStyle(style_tableau(len(lignes))))
    elements += [KeepTogether([titre_section(2, "Opérateurs et accusés de réception"), Spacer(1, 3 * mm), tableau_ops]),
                 Spacer(1, 7 * mm)]

    # ======================= 3. CHRONOLOGIE =======================
    chrono = construire_chronologie(incident)
    lignes = [[p(x, STYLE_ENTETE) for x in ("Date et heure", "Événement", "Détail", "Alertés / informés", "Par")]]
    fonds = []
    for i, l in enumerate(chrono, start=1):
        lignes.append([
            p(date_fr(l['date'], secondes=True)),
            Paragraph(f"<b>{texte(l['titre'])}</b>" + (f"<br/><font size=7.5 color='#9a4a12'><b>{texte(l['escalade'])}</b></font>"
                                                        if l['escalade'] else ''), STYLE),
            p(l['detail'] + (f" ({l['note']})" if l['note'] else '')),
            p(", ".join(l['operateurs']) or '—'),
            p(l['par'], STYLE_PETIT),
        ])
        if l['categorie'] == 'escalade':
            fonds.append(('BACKGROUND', (0, i), (-1, i), ORANGE_CLAIR))
        elif l['type'] in (Evenement.OUVERTURE,):
            fonds.append(('BACKGROUND', (0, i), (-1, i), ROUGE_CLAIR))
        elif l['type'] in (Evenement.RESOLUTION,):
            fonds.append(('BACKGROUND', (0, i), (-1, i), VERT_CLAIR))
        elif l['type'] in (Evenement.CLOTURE,):
            fonds.append(('BACKGROUND', (0, i), (-1, i), FOND))
        elif l['categorie'] == 'operateur':
            fonds.append(('BACKGROUND', (0, i), (-1, i), VIOLET_CLAIR))
    tableau_chrono = Table(lignes, colWidths=[31 * mm, 37 * mm, 58 * mm, 27 * mm, 21 * mm], repeatRows=1)
    tableau_chrono.setStyle(TableStyle(style_tableau(len(lignes), alterner=False) + fonds))
    legende = Paragraph(
        "<font color='#8b8f9a'>Couleurs : <font color='#a32424'>rouge</font> = ouverture, "
        "<font color='#9a4a12'>orange</font> = escalade, <font color='#6b4fb0'>violet</font> = action d'un opérateur, "
        "<font color='#0a6e0a'>vert</font> = retour à la normale, gris = clôture.</font>", STYLE_PETIT)
    elements += [titre_section(3, "Chronologie de l'incident"), Spacer(1, 3 * mm), tableau_chrono,
                 Spacer(1, 2 * mm), legende, Spacer(1, 7 * mm)]

    # ======================= 4. DISCUSSION =======================
    commentaires = incident.evenements.filter(type=Evenement.COMMENTAIRE).select_related('auteur', 'operateur')
    bloc = [titre_section(4, "Discussion entre opérateurs"), Spacer(1, 3 * mm)]
    if commentaires:
        lignes = [[p(x, STYLE_ENTETE) for x in ("Date", "Auteur", "Message")]]
        for c in commentaires:
            auteur = c.operateur.get_niveau_display() if c.operateur else f"{c.auteur.username if c.auteur else '?'} (admin)"
            lignes.append([p(date_fr(c.date)), p(auteur, STYLE_GRAS), p(c.message)])
        tableau_disc = Table(lignes, colWidths=[29 * mm, 30 * mm, 115 * mm], repeatRows=1)
        tableau_disc.setStyle(TableStyle(style_tableau(len(lignes))))
        bloc.append(tableau_disc)
    else:
        bloc.append(p("Aucun commentaire.", STYLE_PETIT))
    elements += [KeepTogether(bloc), Spacer(1, 7 * mm)]

    # ======================= 5. CLÔTURE ET VALIDATION =======================
    raison = cloture.message.split(' : ', 1)[1] if cloture and ' : ' in cloture.message else "—"
    tableau_raison = Table([
        [p("Cause / raison de la clôture", STYLE_LABEL)],
        [p(raison if cloture else "Incident non clôturé à la date d'édition.", STYLE)],
    ], colWidths=[174 * mm])
    tableau_raison.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BORDURE),
        ('BACKGROUND', (0, 0), (-1, 0), FOND),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))

    def case_signature(titre):
        return [
            [p(titre, STYLE_GRAS)],
            [p("Nom :", STYLE_LABEL)],
            [p("Date :", STYLE_LABEL)],
            [p("Signature :", STYLE_LABEL)],
            [''],
        ]

    signatures = Table(
        [[Table(case_signature("Opérateur responsable"), colWidths=[84 * mm], rowHeights=[7 * mm, 7 * mm, 7 * mm, 6 * mm, 16 * mm]),
          Table(case_signature("Administrateur"), colWidths=[84 * mm], rowHeights=[7 * mm, 7 * mm, 7 * mm, 6 * mm, 16 * mm])]],
        colWidths=[87 * mm, 87 * mm],
    )
    signatures.setStyle(TableStyle([
        ('BOX', (0, 0), (0, 0), 0.6, BORDURE),
        ('BOX', (1, 0), (1, 0), 0.6, BORDURE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(KeepTogether([
        titre_section(5, "Clôture et validation"), Spacer(1, 3 * mm),
        tableau_raison, Spacer(1, 4 * mm), signatures,
    ]))

    # ======================= GÉNÉRATION =======================
    infos_pied = (f"Fiche incident n° {incident.pk} — éditée le {date_fr(timezone.now())} "
                  f"par {utilisateur.username} — Surveillance IoT")
    doc.build(elements, canvasmaker=lambda *a, **k: CanvasNumerote(*a, infos_pied=infos_pied, **k))
    return tampon.getvalue()
