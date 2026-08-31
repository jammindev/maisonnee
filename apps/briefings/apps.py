from django.apps import AppConfig


class BriefingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "briefings"

    def ready(self):
        from core.visibility import (
            PrivacySpec,
            register as register_privacy,
            visible_to_creator,
        )
        from .models import Briefing

        # Un briefing privé n'appartient qu'à qui l'a écrit.
        #
        # ``Briefing`` n'est pas searchable, et c'est précisément pourquoi il avait
        # besoin du registre : tant que la confidentialité se déclarait sur le
        # ``SearchableSpec``, un modèle privatisable mais non cherchable n'avait
        # nulle part où se déclarer — son viewset réécrivait donc la règle à la
        # main, quatrième exemplaire du même ``Q``.
        register_privacy(PrivacySpec(model=Briefing, narrow=visible_to_creator))
