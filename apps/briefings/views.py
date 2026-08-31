"""Briefings REST API."""
import logging


from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from agent.llm import LLMError, LLMTimeoutError
from core.permissions import IsHouseholdMember
from core.visibility import narrow_for

from .conditions import evaluate_condition
from .generation import generate_briefing_text, send_briefing_now
from .models import Briefing
from .permissions import CanManageBriefing
from .serializers import BriefingSendLogSerializer, BriefingSerializer
from .services import create_briefing, update_briefing

logger = logging.getLogger(__name__)

HISTORY_PAGE_SIZE = 30


class BriefingViewSet(viewsets.ModelViewSet):
    """CRUD for a household's briefings.

    The list is visibility-filtered: every member sees the household's **shared**
    briefings plus their **own private** ones. Writes delegate to
    ``briefings.services`` (the single write path).
    """

    permission_classes = [IsHouseholdMember, CanManageBriefing]
    serializer_class = BriefingSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Briefing.objects.for_user_households(self.request.user).select_related(
            "created_by"
        )
        if self.request.household:
            qs = qs.filter(household=self.request.household)
        # Un briefing privé n'appartient qu'à qui l'a écrit — règle déclarée dans
        # ``briefings.apps`` et appliquée ici par le point unique.
        return narrow_for(qs, self.request.user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        briefing = create_briefing(
            self.request.household,
            self.request.user,
            title=data.get("title", ""),
            prompt=data.get("prompt", ""),
            condition=data.get("condition", ""),
            channel=data.get("channel", Briefing.Channel.TELEGRAM),
            briefing_type=data.get("briefing_type", Briefing.Type.RECURRING),
            is_private=data.get("is_private", False),
            is_active=data.get("is_active", False),
            send_times=data.get("send_times", []),
            weekdays=data.get("weekdays", []),
        )
        serializer.instance = briefing

    def perform_update(self, serializer):
        update_briefing(
            self.request.household,
            self.request.user,
            serializer.instance,
            fields=serializer.validated_data,
        )

    def get_permissions(self):
        # Preview is a read-grade action (generate, no side effect): any member
        # who can *see* the briefing may preview it — the queryset already hides
        # others' private briefings (404). Sending is a manage action.
        if self.action in ("preview", "history"):
            return [IsHouseholdMember()]
        return [IsHouseholdMember(), CanManageBriefing()]

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Recent send attempts for this briefing (lot 5) — read-grade access."""
        briefing = self.get_object()
        logs = briefing.send_logs.select_related("user").order_by("-created_at")[
            :HISTORY_PAGE_SIZE
        ]
        return Response(BriefingSendLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """Generate the briefing content for the requesting user — no Telegram send.

        Also evaluates the condition (if any) so the UI can show whether the
        briefing would actually go out right now.
        """
        briefing = self.get_object()
        try:
            text = generate_briefing_text(briefing, recipient=request.user)
        except (LLMTimeoutError, LLMError):
            logger.warning("briefings.preview: LLM error for briefing=%s", briefing.pk)
            return Response(
                {"detail": "generation_failed"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        condition_verdict = None
        if (briefing.condition or "").strip():
            verdict = evaluate_condition(briefing, recipient=request.user)
            condition_verdict = {"send": verdict.send, "reason": verdict.reason}

        return Response({"text": text, "condition_verdict": condition_verdict})

    @action(detail=True, methods=["post"], url_path="send-now")
    def send_now(self, request, pk=None):
        """Generate + push the briefing to its recipients right now (manual)."""
        briefing = self.get_object()
        summary = send_briefing_now(briefing, triggered_by=request.user)
        return Response(summary)
