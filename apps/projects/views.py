import logging

from django.utils import timezone
from rest_framework import status as drf_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app_settings import capabilities
from core.permissions import IsHouseholdMember
from documents.mixins import DocumentLinkActionsMixin
from interactions.services import create_expense_interaction, validate_expense_budget
from .assistant import next_step
from .throttles import ProjectAssistantThrottle
from .models import (
    Project,
    ProjectGroup,
    ProjectZone,
    UserPinnedProject,
)
from .serializers import (
    AssistantStepSerializer,
    ProjectPlanSerializer,
    ProjectSerializer,
    ProjectGroupSerializer,
    ProjectPurchaseSerializer,
    ProjectZoneSerializer,
)
from .services import annotate_actual_cost, create_project_from_plan

logger = logging.getLogger(__name__)


class _HouseholdScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsHouseholdMember]

    def get_queryset(self):
        queryset = self.model.objects.for_user_households(self.request.user)
        selected_household = self.request.household
        if selected_household:
            queryset = queryset.filter(household=selected_household)
        return queryset

    def perform_create(self, serializer):
        household = self.request.household
        if not household:
            raise ValidationError({"household_id": "A valid household context is required."})
        serializer.save(household=household, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ProjectGroupViewSet(_HouseholdScopedViewSet):
    model = ProjectGroup
    serializer_class = ProjectGroupSerializer


class ProjectViewSet(DocumentLinkActionsMixin, _HouseholdScopedViewSet):
    model = Project
    serializer_class = ProjectSerializer
    document_link_role = "supporting"

    def get_queryset(self):
        queryset = super().get_queryset()
        zone_id = self.request.query_params.get('zone', '').strip()
        if zone_id:
            queryset = queryset.filter(project_zones__zone_id=zone_id).distinct()
        status = self.request.query_params.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        return annotate_actual_cost(queryset)

    def perform_create(self, serializer):
        household = self.request.household
        if not household:
            raise ValidationError({"household_id": "A valid household context is required."})

        project_group = serializer.validated_data.get("project_group")
        cover_interaction = serializer.validated_data.get("cover_interaction")

        if project_group and project_group.household_id != household.id:
            raise ValidationError({"project_group": "Project group household must match selected household."})

        if cover_interaction and cover_interaction.household_id != household.id:
            raise ValidationError({"cover_interaction": "Cover interaction household must match selected household."})

        serializer.save(household=household, created_by=self.request.user)

    def perform_update(self, serializer):
        household = self.request.household or serializer.instance.household
        project_group = serializer.validated_data.get("project_group", serializer.instance.project_group)
        cover_interaction = serializer.validated_data.get("cover_interaction", serializer.instance.cover_interaction)

        if project_group and project_group.household_id != household.id:
            raise ValidationError({"project_group": "Project group household must match selected household."})

        if cover_interaction and cover_interaction.household_id != household.id:
            raise ValidationError({"cover_interaction": "Cover interaction household must match selected household."})

        serializer.save(updated_by=self.request.user)

    def get_throttles(self):
        """Un tour d'entretien achète un appel au modèle : cap à part.

        Le plancher global compte des requêtes, pas des euros — même règle que
        `document_upload`, `ocr_reprocess` et `hunt_riddles`.
        """
        if self.action == "assistant_step":
            return [ProjectAssistantThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["post"], url_path="assistant-step")
    def assistant_step(self, request):
        """Le tour suivant de l'entretien de création — et n'écrit **rien**.

        Volontairement une action de **liste** : le projet n'existe pas encore,
        et c'est tout le sujet. Une route de détail obligerait à enregistrer un
        chantier vide avant de pouvoir en parler — exactement le formulaire qu'on
        remplace. Ici « rien n'est écrit » n'est même plus une promesse à tenir :
        l'endpoint ne sait pas où écrire. La création est un endpoint séparé
        (lot 2), et cette séparation est ce qui rend la garantie structurelle
        plutôt que dépendante d'un `if`.

        ⚠️ `url_path` est explicite parce que DRF **ne dérive pas** le chemin du
        nom de la méthode de la même façon que le nom de route : `url_name`
        remplace les underscores par des tirets, `url_path` non. Sans cette ligne
        le front appellerait `/assistant-step/` pendant que le serveur servirait
        `/assistant_step/`, et tout test passant par `reverse()` resterait vert.
        """
        # Avant tout effet de bord — et surtout avant l'appel qui coûte : un 200
        # inventé ou un 500 diraient tous deux « le produit est cassé », alors
        # qu'il manque une clé et que quelqu'un peut la poser.
        capabilities.require("project_assistant")

        household = getattr(request, "household", None)
        if household is None:
            raise ValidationError({"household_id": "A valid household context is required."})

        serializer = AssistantStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            step = next_step(
                household,
                goal=serializer.validated_data["goal"],
                history=serializer.validated_data["history"],
                force_ready=serializer.validated_data["force_ready"],
                user=request.user,
            )
        except ValueError as exc:
            # Forme inattendue : rien n'est rendu, et le front garde la question
            # précédente en proposant de reformuler. Un demi-plan serait pire —
            # l'écran de relecture afficherait des lignes vides sans dire
            # lesquelles viennent du modèle.
            logger.warning("projects.assistant: step refused (%s)", exc)
            return Response({"detail": str(exc)}, status=drf_status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:  # noqa: BLE001 — panne fournisseur, pas un bug d'ici
            logger.warning("projects.assistant: step failed (%s)", exc)
            return Response(
                {"detail": "The assistant could not answer right now."},
                status=drf_status.HTTP_502_BAD_GATEWAY,
            )

        return Response(_serialize_step(step))

    @action(detail=False, methods=["post"], url_path="assistant-create")
    def assistant_create(self, request):
        """Écrit le plan relu — projet, tâches, notes — en une transaction.

        **Pas de `capabilities.require` ici, et c'est voulu** : créer un projet ne
        demande aucune clé. Un plan déjà obtenu doit rester créable si la clé
        tombe entre-temps — refuser ferait perdre à l'utilisateur un travail de
        relecture qu'il vient de faire, pour une raison qui ne le concerne plus.

        C'est aussi la moitié « écriture » de la séparation en deux endpoints :
        celui-ci ne parle à aucun modèle, celui de l'entretien ne sait pas écrire.
        La garantie « rien n'est écrit avant relecture » tient à ça, pas à un
        `if`.
        """
        household = getattr(request, "household", None)
        if household is None:
            raise ValidationError({"household_id": "A valid household context is required."})

        serializer = ProjectPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = create_project_from_plan(
            household, request.user, plan=serializer.validated_data
        )

        # Relu à travers le queryset annoté pour que la réponse porte
        # `actual_cost_cached` et les zones, comme n'importe quelle lecture.
        project = self.get_queryset().get(pk=project.pk)
        payload = ProjectSerializer(project, context={"request": request}).data
        return Response(payload, status=drf_status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="register-purchase")
    def register_purchase(self, request, pk=None):
        """Create an Interaction(type=expense) linked to the project.

        The project's actual cost is computed from its expense interactions
        (#234) — this endpoint only creates the interaction, nothing to sync.
        """
        project = self.get_object()
        serializer = ProjectPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        budget_id = validate_expense_budget(
            project.household_id, serializer.validated_data.get("budget_id")
        )

        interaction = create_expense_interaction(
            source=project,
            user=request.user,
            amount=serializer.validated_data.get("amount"),
            supplier=serializer.validated_data.get("supplier", "") or "",
            occurred_at=serializer.validated_data.get("occurred_at") or timezone.now(),
            notes=serializer.validated_data.get("notes", "") or "",
            kind="project_purchase",
            budget_id=budget_id,
            extra_metadata={"project_title": project.title},
        )

        # Re-fetch through the annotated queryset so the response includes the
        # freshly created expense in actual_cost_cached.
        project = self.get_queryset().get(pk=project.pk)
        payload = ProjectSerializer(project, context={"request": request}).data
        payload["interaction_id"] = str(interaction.id)
        return Response(payload, status=drf_status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="pin")
    def pin(self, request, pk=None):
        project = self.get_object()
        household = request.household or project.household
        member = request.user.householdmember_set.filter(household=household).first()
        if not member:
            raise ValidationError({"detail": "No household membership found."})
        UserPinnedProject.objects.get_or_create(household_member=member, project=project)
        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="unpin")
    def unpin(self, request, pk=None):
        project = self.get_object()
        household = request.household or project.household
        member = request.user.householdmember_set.filter(household=household).first()
        if member:
            UserPinnedProject.objects.filter(household_member=member, project=project).delete()
        serializer = self.get_serializer(project)
        return Response(serializer.data)


class ProjectZoneViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsHouseholdMember]
    serializer_class = ProjectZoneSerializer

    def get_queryset(self):
        queryset = ProjectZone.objects.filter(
            project__household_id__in=self.request.user.householdmember_set.values_list("household_id", flat=True)
        )
        selected_household = self.request.household
        if selected_household:
            queryset = queryset.filter(project__household=selected_household)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        zone = serializer.validated_data["zone"]
        if not Project.objects.for_user_households(self.request.user).filter(id=project.id).exists():
            raise ValidationError({"project": "Invalid project or access denied."})
        if not zone.__class__.objects.for_user_households(self.request.user).filter(id=zone.id).exists():
            raise ValidationError({"zone": "Invalid zone or access denied."})
        if project.household_id != zone.household_id:
            raise ValidationError({"zone": "Zone household must match project household."})
        serializer.save(created_by=self.request.user)


def _serialize_step(step) -> dict:
    """La forme que le front lit — une question, ou le plan, jamais les deux."""
    payload = {
        "state": step.state,
        "asked": step.asked,
        "remaining": step.remaining,
    }
    if step.question is not None:
        payload["question"] = {
            "text": step.question.text,
            "field": step.question.field,
            "input": step.question.input,
            "hint": step.question.hint,
            "choices": list(step.question.choices),
        }
    if step.plan is not None:
        payload["plan"] = {
            "project": step.plan.project,
            "tasks": list(step.plan.tasks),
            "notes": list(step.plan.notes),
        }
    return payload
