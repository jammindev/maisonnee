from rest_framework import serializers
from .models import Notification
from .service import deep_link_for


class NotificationSerializer(serializers.ModelSerializer):
    # Le lien **résolu**, jamais la colonne brute. `deep_link_for` n'était
    # appelée que par le miroir Web Push : une alerte météo menait donc à sa page
    # depuis la notification système et **nulle part** depuis la cloche, faute de
    # `url` sur la ligne. Un même fait ne peut pas avoir deux destinations — et
    # celle qui manquait était celle qu'on lit dans l'app.
    url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "payload", "url", "is_read", "read_at", "created_at"]
        read_only_fields = fields

    def get_url(self, obj) -> str:
        return deep_link_for(obj)
