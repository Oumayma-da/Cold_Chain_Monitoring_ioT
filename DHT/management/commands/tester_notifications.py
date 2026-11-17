"""
Envoie un message de TEST à chaque opérateur (Gmail + Telegram)
pour vérifier la configuration, sans créer d'incident.

    python manage.py tester_notifications
    python manage.py tester_notifications --niveau 2     (un seul opérateur)
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from DHT.models import Operateur
from DHT.notifications import notifier_operateur


class Command(BaseCommand):
    help = "Envoie une notification de test à chaque opérateur"

    def add_arguments(self, parser):
        parser.add_argument('--niveau', type=int, help="Seulement cet opérateur (1, 2 ou 3)")

    def handle(self, *args, **options):
        self.stdout.write(f"Gmail    : {'configuré (' + settings.EMAIL_HOST_USER + ')' if settings.EMAIL_HOST_PASSWORD else 'NON configuré -> email affiché dans ce terminal'}")
        self.stdout.write(f"Telegram : {'configuré' if settings.TELEGRAM_TOKEN else 'NON configuré'}")
        self.stdout.write(f"Notifications actives : {settings.NOTIFICATIONS_ACTIVES}\n")

        operateurs = Operateur.objects.select_related('user')
        if options['niveau']:
            operateurs = operateurs.filter(niveau=options['niveau'])
        if not operateurs:
            self.stdout.write(self.style.ERROR("Aucun opérateur. Lance d'abord : python manage.py creer_operateurs"))
            return

        for op in operateurs:
            texte = (f"Bonjour {op.get_niveau_display()},\n\n"
                     f"Ceci est un message de TEST de la surveillance IoT.\n"
                     f"Si tu le reçois, tes alertes sont bien configurées. ✅")
            resultat = notifier_operateur(op, f"[TEST] Notification {op.get_niveau_display()}", texte)
            style = self.style.SUCCESS if '✗' not in resultat else self.style.WARNING
            self.stdout.write(style(f"{op} : {resultat}"))
