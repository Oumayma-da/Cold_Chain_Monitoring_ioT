# Cold Chain Monitoring IoT

Surveillance de la température et de l'humidité avec un capteur DHT11 et Django.

## Fonctionnalités (étapes faites)
- Tableau de bord temps réel (cartes Température / Humidité, état du capteur)
- Graphiques avec filtres (1h, 24h, 7j, 30j, tout, dates personnalisées) et statistiques
- Admin : insertion de mesures de test
- Admin : seuils modifiables (normal / attention / critique)

## Installation
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

## Pages
| URL | Rôle |
|---|---|
| `/dashboard/` | Tableau de bord |
| `/graphique/temp/` et `/graphique/hum/` | Graphiques |
| `/test/inserer/` | Insérer une mesure de test (admin) |
| `/parametres/seuils/` | Modifier les seuils (admin) |
| `/api/post` | Réception des mesures de l'ESP |