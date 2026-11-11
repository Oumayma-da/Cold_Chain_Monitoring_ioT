import telebot

from django.conf import settings
from django.core.mail import send_mail


def verifier_alertes(temperature):
    """Envoie Gmail et Telegram si la température dépasse 25 °C."""

    if temperature is None or temperature <= 25:
        return

    message = f"Alerte IoT ! Température = {temperature} °C"

    # Notification Gmail
    send_mail(
        subject="Alerte Température IoT",
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[settings.EMAIL_HOST_USER],
        fail_silently=False
    )

    # Notification Telegram
    bot = telebot.TeleBot(settings.TELEGRAM_TOKEN)
    bot.send_message(settings.TELEGRAM_CHAT_ID, message)