"""
Crée (ou met à jour) les 3 opérateurs de test : op1, op2, op3.

    python manage.py creer_operateurs
    python manage.py creer_operateurs --mot-de-passe MonMotDePasse
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from DHT.models import Operateur


class Command(BaseCommand):
    help = "Crée les comptes op1, op2, op3 (Opérateur 1, 2 et 3)"

    def add_arguments(self, parser):
        parser.add_argument('--mot-de-passe', default='operateur123')

    def handle(self, *args, **options):
        mot_de_passe = options['mot_de_passe']
        for niveau in (1, 2, 3):
            nom = f"op{niveau}"
            user, cree = User.objects.get_or_create(
                username=nom,
                defaults={'first_name': 'Opérateur', 'last_name': str(niveau)},
            )
            if cree:
                user.set_password(mot_de_passe)
                user.save()
            Operateur.objects.update_or_create(niveau=niveau, defaults={'user': user})
            etat = "créé" if cree else "déjà existant (mot de passe inchangé)"
            self.stdout.write(self.style.SUCCESS(f"Opérateur {niveau} : {nom} {etat}"))
        self.stdout.write(f"Mot de passe des nouveaux comptes : {mot_de_passe}")
        self.stdout.write("Ajoute l'email / le chat ID Telegram de chacun dans Admin > Opérateurs et Admin > Utilisateurs.")
