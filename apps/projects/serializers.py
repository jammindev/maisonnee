from decimal import Decimal

from rest_framework import serializers

from zones.models import Zone

from .models import (
    Project,
    ProjectGroup,
    ProjectZone,
    UserPinnedProject,
)
from .assistant import MAX_NOTES, MAX_QUESTIONS, MAX_TASKS
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
            "default_budget",
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
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None
        return project_tab_counts(obj, viewer)

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
        # Un service métier n'a pas de `request` — l'agent n'en a jamais eu, la
        # création assistée non plus. Sans lui on borne au foyer **du projet**,
        # ce qui est *plus* strict que le scope multi-foyers d'un appelant HTTP :
        # le contrôle d'appartenance juste en dessous reste vrai dans les deux cas.
        if request is not None:
            candidates = Zone.objects.for_user_households(request.user)
        else:
            candidates = Zone.objects.filter(household_id=project.household_id)
        zones = list(candidates.filter(id__in=ids))
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



class PlanBudgetSerializer(serializers.Serializer):
    """L'enveloppe du chantier, telle que l'écran l'a proposée puis relue.

    Deux modes, et pas un troisième : soit une enveloppe **qui existe** (par son
    id, résolu au tour d'entretien), soit une **à créer** (par son nom). Le
    « aucune » se dit en envoyant `null` sur le champ, pas par un mode de plus —
    un mode « none » porteur d'un nom vide finirait par exister quelque part.
    """

    mode = serializers.ChoiceField(choices=["existing", "new"])
    id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["mode"] == "existing" and not attrs.get("id"):
            raise serializers.ValidationError(
                {"id": "An existing envelope needs its id."}
            )
        if attrs["mode"] == "new" and not (attrs.get("name") or "").strip():
            raise serializers.ValidationError(
                {"name": "A new envelope needs a name."}
            )
        return attrs


class PlanTaskSerializer(serializers.Serializer):
    """Une tâche du plan, telle que l'utilisateur l'a relue et corrigée.

    `zone_ids` porte des **ids**, jamais des noms : la résolution nom → id a déjà
    eu lieu au tour d'entretien (`assistant.resolve_plan_zones`), pour que l'écran
    affiche des pièces réelles avant que rien ne soit écrit. Accepter des noms ici
    rouvrirait un second chemin de désignation, donc deux définitions de « la
    chambre ».
    """

    subject = serializers.CharField(max_length=500)
    content = serializers.CharField(allow_blank=True, default="")
    priority = serializers.IntegerField(
        min_value=1, max_value=5, required=False, allow_null=True
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    zone_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=10
    )


class PlanNoteSerializer(serializers.Serializer):
    """Une note du plan. Pas de priorité ni d'échéance : une note n'est pas une
    tâche, et lui en donner ferait des notes une deuxième liste de choses à
    faire."""

    subject = serializers.CharField(max_length=500)
    content = serializers.CharField(allow_blank=True, default="")
    zone_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=10
    )


class PlanProjectSerializer(serializers.Serializer):
    """Le projet du plan.

    `type` et `priority` sont nullables parce que le moteur **retire** une valeur
    qu'il n'a pas su valider plutôt que de la deviner : le champ arrive donc vide,
    et le défaut du modèle s'applique.
    """

    title = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, default="")
    type = serializers.ChoiceField(
        choices=Project.Type.choices, required=False, allow_null=True
    )
    priority = serializers.IntegerField(
        min_value=1, max_value=5, required=False, allow_null=True
    )
    planned_budget = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=60),
        required=False,
        default=list,
        max_length=10,
    )
    zone_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=10
    )
    budget = PlanBudgetSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        """Deux dates incohérentes se refusent ici, pas dans Postgres.

        `projects_dates_consistent` est un `CheckConstraint` : sans ce contrôle,
        un plan où le modèle a daté la fin avant le début produit une
        `IntegrityError`, donc un **500** sur une erreur de contenu parfaitement
        ordinaire.
        """
        start, due = attrs.get("start_date"), attrs.get("due_date")
        if start and due and due < start:
            raise serializers.ValidationError(
                {"due_date": "The due date cannot precede the start date."}
            )
        return attrs


class ProjectPlanSerializer(serializers.Serializer):
    """Entrée de `POST /api/projects/projects/assistant-create/`.

    ⚠️ Ce n'est **pas** une sortie de modèle qu'on revalide : entre la génération
    et cet appel, l'humain a réécrit des titres, corrigé un montant et décoché des
    lignes. Ce qui arrive ici est du contenu **utilisateur**, et se valide comme
    n'importe quel POST. Les plafonds sont ceux du moteur (`MAX_TASKS` /
    `MAX_NOTES`) pour que le refus soit le même des deux côtés : un plan que
    l'entretien n'aurait pas produit ne doit pas pouvoir entrer par cette porte.
    """

    project = PlanProjectSerializer()
    tasks = serializers.ListField(
        child=PlanTaskSerializer(), required=False, default=list, max_length=MAX_TASKS
    )
    notes = serializers.ListField(
        child=PlanNoteSerializer(), required=False, default=list, max_length=MAX_NOTES
    )


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
