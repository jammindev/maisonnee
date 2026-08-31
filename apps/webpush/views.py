from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_settings.capabilities import require as require_capability

from .models import WebPushSubscription
from .serializers import SubscribeSerializer, UnsubscribeSerializer
from .service import send_web_push


class VapidPublicKeyView(APIView):
    """Public VAPID key the browser needs to create a subscription."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Sans paire VAPID, renvoyer 200 + une clé vide faisait échouer
        # `pushManager.subscribe()` sur un `InvalidAccessError` illisible, une
        # fois le clic donné. Le refus se dit ici, où il reste explicable.
        require_capability("push")
        return Response({"publicKey": getattr(settings, "VAPID_PUBLIC_KEY", "")})


class SubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Un abonnement que rien ne pourra honorer est pire qu'un refus : il
        # s'enregistre, l'écran dit « activé », et aucune notification n'arrive.
        require_capability("push")
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        endpoint = serializer.validated_data["endpoint"]
        keys = serializer.validated_data["keys"]
        # Keyed on endpoint (unique per browser): re-subscribing the same device
        # updates its keys / owner instead of piling up duplicate rows.
        sub, created = WebPushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": keys["p256dh"],
                "auth": keys["auth"],
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:400],
            },
        )
        return Response(
            {"id": str(sub.id)},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UnsubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        WebPushSubscription.objects.filter(
            user=request.user, endpoint=serializer.validated_data["endpoint"]
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestPushView(APIView):
    """Send a push to the current user — bout-en-bout diagnostic for the UI toggle."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        require_capability("push")
        sent = send_web_push(
            request.user,
            "Maisonnée",
            "🔔 Notification de test",
            url="/app/dashboard",
            tag="webpush-test",
            # Demo badge so the test also exercises the app-icon Badging API. It
            # resyncs to the real unread count as soon as the SPA reopens.
            data={"unreadCount": 1},
        )
        return Response({"sent": sent})
