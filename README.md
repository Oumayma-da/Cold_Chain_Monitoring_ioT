# Cold Chain Monitoring IoT

Surveillance de la température et de l'humidité avec un capteur DHT11 et Django.

## Fonctionnalités
- Tableau de bord temps réel (cartes Température / Humidité, état du capteur, bandeau incident en cours)
- Graphiques avec filtres (1h, 24h, 7j, 30j, tout, dates personnalisées), statistiques et **export CSV**
- Admin : insertion de mesures de test
- Admin : seuils min / max modifiables (frigo catalyseurs : 2 à 8 °C)
- **Incidents** : ouverture automatique hors limites, compteur, escalade Opérateur 1 → 2 → 3,
  accusé de réception, discussion, journal chronologique, résolution automatique, clôture et **fiche PDF** (admin)
- Notifications Gmail + Telegram envoyées à chaque opérateur selon l'escalade (contacts dans Admin > Opérateurs, secrets dans `.env`)

## Installation
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py creer_operateurs      # op1, op2, op3 (mot de passe : operateur123)
python manage.py tester_notifications  # vérifie Gmail + Telegram
python manage.py runserver 0.0.0.0:8000
```

## Pages
| URL | Rôle |
|---|---|
| `/dashboard/` | Tableau de bord |
| `/graphique/temp/` et `/graphique/hum/` | Graphiques |
| `/test/inserer/` | Insérer une mesure de test (admin) |
| `/parametres/seuils/` | Modifier les seuils (admin) |
| `/incidents/` | Liste des incidents (connexion requise) |
| `/incidents/<id>/` | Détail : accusés, discussion, journal, clôture |
| `/connexion/` | Connexion opérateurs / admin |
| `/export/mesures.csv` | Export CSV des mesures |
| `/api/post` | Réception des mesures de l'ESP |