import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField

from core.models import HouseholdScopedModel
from core.managers import HouseholdScopedManager


class ProjectGroup(HouseholdScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    description = models.TextField(default="")
    tags = ArrayField(models.TextField(), default=list, blank=True)

    objects = HouseholdScopedManager()

    class Meta:
        db_table = "project_groups"


class Project(HouseholdScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Type(models.TextChoices):
        RENOVATION = "renovation", "Renovation"
        MAINTENANCE = "maintenance", "Maintenance"
        REPAIR = "repair", "Repair"
        PURCHASE = "purchase", "Purchase"
        RELOCATION = "relocation", "Relocation"
        VACATION = "vacation", "Vacation"
        LEISURE = "leisure", "Leisure"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField()
    description = models.TextField(default="")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    priority = models.IntegerField(default=3)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    tags = ArrayField(models.TextField(), default=list, blank=True)
    planned_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cost_cached = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cover_interaction = models.ForeignKey("interactions.Interaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="cover_for_projects")
    project_group = models.ForeignKey(ProjectGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.OTHER)
    is_private = models.BooleanField(
        default=False,
        help_text=(
            "Privé : seul le créateur voit ce chantier — et, par héritage, tout ce "
            "qu'il contient. La visibilité des enfants se CALCULE à la lecture "
            "(core.visibility) ; rien n'est écrit sur eux, sinon dé-privatiser ne "
            "saurait plus ce qui était privé avant."
        ),
    )
    document_links = GenericRelation("documents.DocumentLink")

    objects = HouseholdScopedManager()

    class Meta:
        db_table = "projects"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(priority__gte=1) & models.Q(priority__lte=5),
                name="projects_priority_between_1_5",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_budget__gte=0),
                name="projects_planned_budget_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_cost_cached__gte=0),
                name="projects_actual_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(start_date__isnull=True)
                    | models.Q(due_date__isnull=True)
                    | models.Q(due_date__gte=models.F("start_date"))
                ),
                name="projects_dates_consistent",
            ),
        ]


class UserPinnedProject(models.Model):
    household_member = models.ForeignKey(
        "households.HouseholdMember",
        on_delete=models.CASCADE,
        related_name="pinned_projects",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="pinned_by_members",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_member_pins"
        unique_together = [["household_member", "project"]]
        indexes = [
            models.Index(fields=["household_member"]),
            models.Index(fields=["project"]),
        ]


class ProjectZone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_zones")
    zone = models.ForeignKey("zones.Zone", on_delete=models.CASCADE, related_name="project_zones")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "project_zones"
        unique_together = [["project", "zone"]]


