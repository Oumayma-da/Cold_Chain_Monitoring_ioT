"""
Notifications des opérateurs : Gmail + Telegram.

Chaque opérateur reçoit les alertes sur SES contacts (Admin > Opérateurs) :
    - email            : adresse de l'opérateur
    - telegram_chat_id : son chat Telegram
Si un opérateur n'a pas encore de contact, on utilise ceux du fichier .env
(EMAIL_HOST_USER / TELEGRAM_CHAT_ID), comme dans la première version du projet.

Plus tard (application mobile / APK) : il suffira d'ajouter une fonction
envoyer_mobile() et d'ajouter "mobile" dans settings.CANAUX_NOTIFICATION.
"""
from django.conf import settings
from django.core.mail import send_mail


# ---------------------------------------------------------
# Canal 1 : Gmail
# ---------------------------------------------------------
def envoyer_email(operateur, sujet, message):
    destinataire = operateur.user.email or settings.EMAIL_HOST_USER
    if not destinataire:
        return "email ✗ (aucune adresse)"
    try:
        send_mail(
            subject=sujet,
            message=message,
            from_email=settings.EMAIL_HOST_USER or "iot@localhost",
            recipient_list=[destinataire],
            fail_silently=False,
        )
        return f"email ✓ ({destinataire})"
    except Exception as erreur:
        return f"email ✗ ({erreur.__class__.__name__})"


# ---------------------------------------------------------
# Canal 2 : Telegram
# ---------------------------------------------------------
def envoyer_telegram(operateur, sujet, message):
    chat_id = operateur.telegram_chat_id or settings.TELEGRAM_CHAT_ID
    if not settings.TELEGRAM_TOKEN:
        return "Telegram ✗ (token non configuré)"
    if not chat_id:
        return "Telegram ✗ (aucun chat ID)"
    try:
        import telebot
        telebot.apihelper.CONNECT_TIMEOUT = 10   # ne pas bloquer si Telegram ne répond pas
        telebot.apihelper.READ_TIMEOUT = 10
        bot = telebot.TeleBot(settings.TELEGRAM_TOKEN)
        bot.send_message(chat_id, message)
        return "Telegram ✓"
    except Exception as erreur:
        return f"Telegram ✗ ({erreur.__class__.__name__})"


# Liste des canaux disponibles (on ajoutera "mobile" pour l'APK)
CANAUX = {
    'email': envoyer_email,
    'telegram': envoyer_telegram,
}


def notifier_operateur(operateur, sujet, message):
    """Envoie le message à un opérateur sur chaque canal activé. Renvoie le résumé pour le journal."""
    if not settings.NOTIFICATIONS_ACTIVES:
        return "visible dans l'application (notifications désactivées)"

    resultats = []
    for nom in settings.CANAUX_NOTIFICATION:
        fonction = CANAUX.get(nom)
        if fonction:
            resultats.append(fonction(operateur, sujet, message))
    return ", ".join(resultats) or "aucun canal configuré"
