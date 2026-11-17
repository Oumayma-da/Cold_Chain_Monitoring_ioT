"""Variables disponibles dans TOUS les templates (menu du haut)."""
from .models import Incident


def incidents(request):
    if not request.user.is_authenticated:
        return {}
    return {
        'nb_incidents_ouverts': Incident.objects.filter(statut=Incident.OUVERT).count(),
        'mon_operateur': getattr(request.user, 'operateur', None),
    }
