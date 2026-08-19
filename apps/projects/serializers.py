from decimal import Decimal

from rest_framework import serializers

from zones.models import Zone

from .models import (
    Project,
    ProjectGroup,
    ProjectZone,
    UserPinnedProject,
)
from .assistant import MAX_QUESTIONS
from .services import project_actual_cost, project_tab_counts


class ProjectPurchaseSerializer(serializers.Serializer):
    """Input for /projects/{id}/register-purchase/."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0")
    )
    supplier = serializers.CharField(required=False, allow_blank=True, default="")
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # Enveloppe à laquelle imputer l'achat. Facultative, mais son absence est
    # l'écart `expense_without_budget` : sans budget, un euro n'est classé par
    # aucun axe (projet et zone disent *sur quoi* et *où*, pas *de quelle
    # nature*). L'offrir à la saisie évite de fabriquer l'écart puis de le
    # réparer.
    budget_id = serializers.UUIDField(required=False, allow_null=True)


class ProjectGroupPickerSerializer(serializers.ModelSerializer):
    """Minimal serializer for group picker dropdowns in forms."""

    class Meta:
        model = ProjectGroup
        fields = ["id", "name"]


class ProjectGroupSerializer(serializers.ModelSerializer):
    projects_count = serializers.SerializerMethodField()

    class Meta:
        model = ProjectGroup
        fields = [
            "id",
            "household",
            "name",
            "description",
            "tags",
            "projects_count",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "household", "created_at", "updated_at", "created_by", "updated_by"]

    def get_projects_count(self, obj):
        return obj.projects.count()


class ProjectSerializer(serializers.ModelSerializer):
    is_pinned = serializers.SerializerMethodField()
    zones = serializers.SerializerMethodField()
    zone_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    project_group_name = serializers.SerializerMethodField()
    # Calculé (SUM des Interaction expense liées par la source polymorphe, #234) —
    # la colonne DB du même nom n'est plus jamais écrite. Le nom de champ API est
    # conservé pour ne pas casser les clients.
    actual_cost_cached = serializers.SerializerMethodField()
    # Nombre d'items derrière chaque onglet du détail (tasks, notes, photos…).
    # Renseigné UNIQUEMENT sur le retrieve (detail) — null en liste, pour ne pas
    # payer les counts par projet. Le front masque les onglets à 0.
    tab_counts = serializers.SerializerMethodField()
    # Le modèle a default="" mais pas blank=True : DRF rejette les chaînes vides
    # par défaut. Le formulaire React envoie systématiquement description="" quand
    # l'utilisateur n'écrit rien — rendre le champ optionnel + blank-OK ici.
    description = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Project
        fields = [
            "id",
            "household",
            "title",
            "description",
            "status",
            "priority",
            "start_date",
            "due_date",
            "closed_at",
            "tags",
            "planned_budget",
            "actual_cost_cached",
            "tab_counts",
            "cover_interaction",
            "project_group",
            "project_group_name",
            "type",
            "is_pinned",
            "zones",
            "zone_ids",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "household", "created_at", "updated_at", "created_by", "updated_by"]

    def get_actual_cost_cached(self, obj):
        total = getattr(obj, "actual_cost_computed", None)
        if total is None:
            total = project_actual_cost(obj)
        return str(Decimal(total).quantize(Decimal("0.01")))

    def get_tab_counts(self, obj):
        # Detail seulement : la liste passe view.action == "list" → on n'agrège pas.
        view = self.context.get("view")
        if view is not None and getattr(view, "action", None) != "retrieve":
            return None
        return project_tab_counts(obj)

    def get_is_pinned(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return UserPinnedProject.objects.filter(
            project=obj,
            household_member__user=request.user,
            household_member__household=obj.household,
        ).exists()

    def get_zones(self, obj):
        return [
            {"id": str(pz.zone.id), "name": pz.zone.name, "color": pz.zone.color}
            for pz in obj.project_zones.select_related("zone").all()
        ]

    def get_project_group_name(self, obj):
        return obj.project_group.name if obj.project_group else None

    def create(self, validated_data):
        zone_ids = validated_data.pop("zone_ids", None)
        project = super().create(validated_data)
        if zone_ids is not None:
            self._sync_zones(project, zone_ids)
        return project

    def update(self, instance, validated_data):
        zone_ids = validated_data.pop("zone_ids", None)
        project = super().update(instance, validated_data)
        if zone_ids is not None:
            self._sync_zones(project, zone_ids)
        return project

    def _sync_zones(self, project, zone_ids):
        request = self.context.get("request")
        ids = [str(z) for z in zone_ids]
        zones = list(Zone.objects.for_user_households(request.user).filter(id__in=ids))
        if len(zones) != len(set(ids)):
            raise serializers.ValidationError(
                {"zone_ids": "One or more zones are invalid or inaccessible."}
            )
        for z in zones:
            if z.household_id != project.household_id:
                raise serializers.ValidationError(
                    {"zone_ids": "Zone household must match project household."}
                )
        existing = set(str(pk) for pk in project.project_zones.values_list("zone_id", flat=True))
        desired = set(ids)
        to_remove = existing - desired
        to_add = desired - existing
        if to_remove:
            project.project_zones.filter(zone_id__in=to_remove).delete()
        for zone_id in to_add:
            ProjectZone.objects.create(
                project=project,
                zone_id=zone_id,
                created_by=request.user if request else None,
            )


class ProjectZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectZone
        fields = ["project", "zone", "created_at", "created_by"]
        read_only_fields = ["created_at", "created_by"]



class AssistantTurnSerializer(serializers.Serializer):
    """Un tour déjà joué de l'entretien — question posée, réponse donnée.

    Permissif sur le contenu, strict sur les **bornes** : le corps de la requête
    est le seul état de l'entretien, donc c'est le seul endroit où en borner la
    taille. Sans plafond, un client pourrait faire grossir le prompt sans limite
    — le compteur de questions, lui, vit dans `assistant.next_step`.
    """

    question = serializers.CharField(max_length=500, allow_blank=True, default="")
    field = serializers.CharField(max_length=60, allow_blank=True, default="")
    answer = serializers.CharField(max_length=1000, allow_blank=True, default="")


class AssistantStepSerializer(serializers.Serializer):
    """Entrée de `POST /api/projects/assistant-step/`.

    `history` est plafonné à `MAX_QUESTIONS` entrées : au-delà, l'entretien doit
    conclure de toute façon, donc accepter davantage ne servirait qu'à gonfler le
    prompt. `force_ready` est le « J'ai assez dit » de l'écran — il n'est pas une
    optimisation, c'est la sortie de secours qui empêche l'entretien de retenir
    quelqu'un qui a fini de parler.
    """

    goal = serializers.CharField(max_length=500, trim_whitespace=True)
    history = serializers.ListField(
        child=AssistantTurnSerializer(),
        required=False,
        default=list,
        max_length=MAX_QUESTIONS,
    )
    force_ready = serializers.BooleanField(required=False, default=False)
