# Simplification des seuils : on passe de 6 valeurs à 2 (min / max).
# La table des seuils est recréée (elle ne contient que des réglages,
# les mesures Dht11 ne sont PAS touchées).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("DHT", "0002_seuil"),
    ]

    operations = [
        migrations.DeleteModel(name="Seuil"),
        migrations.CreateModel(
            name="Seuil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("champ", models.CharField(choices=[("temp", "Température"), ("hum", "Humidité")], max_length=10, unique=True, verbose_name="Mesure")),
                ("valeur_min", models.FloatField(verbose_name="Minimum")),
                ("valeur_max", models.FloatField(verbose_name="Maximum")),
                ("modifie_le", models.DateTimeField(auto_now=True, verbose_name="Modifié le")),
            ],
            options={"verbose_name": "Seuil", "verbose_name_plural": "Seuils"},
        ),
    ]
