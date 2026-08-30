"""
Task REST API views.
"""
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsHouseholdMember
from core.visibility import narrow_for
from documents.mixins import DocumentLinkActionsMixin
from documents.models import Document, DocumentLink
from interactions.models import Interaction
from zones.models import Zone
from .models import Task, TaskInteraction
from .notifications import notify_task_created
from .serializers import (
    TaskSerializer,
    TaskDocumentLinkSerializer,
    TaskInteractionLinkSerializer,
)


class TaskViewSet(DocumentLinkActionsMixin, viewsets.ModelViewSet):
    """
    Task CRUD with filtering by status, priority, zone, assigned_to, overdue.
    completed_by and completed_at are auto-managed on status transitions.
    """

    permission_classes = [IsHouseholdMember]
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # ⚠️ Pas de ``is_private`` ici. Exposer le drapeau en filtre donne
    # ``?is_private=true``, c'est-à-dire l'endroit exact où lire les items privés
    # des autres. Le front n'en a jamais eu besoin : ``TasksPanel`` filtre côté
    # client sur ce qui est déjà chargé, donc sur ce que le serveur a bien voulu
    # servir. Un filtre ne doit jamais pouvoir élargir ce que borne le queryset.
    filterset_fields = ['status', 'priority', 'assigned_to', 'project']
    search_fields = ['subject', 'content']
    ordering_fields = ['due_date', 'created_at', 'priority', 'status']
    ordering = ['due_date', 'created_at']

    class Pagination(LimitOffsetPagination):
        default_limit = 200
        max_limit = 500

    pagination_class = Pagination

    def get_queryset(self):
        qs = Task.objects.for_user_households(self.request.user).select_related(
            'created_by', 'completed_by', 'assigned_to', 'project'
        ).prefetch_related(
            'zones', 'tags__tag',
            'document_links__document',
            'task_interactions__interaction',
        )

        if self.request.household:
            qs = qs.filter(household=self.request.household)

        # Confidentialité — une tâche privée n'appartient qu'à qui l'a écrite.
        #
        # Le scope foyer ci-dessus ne dit rien de la confidentialité : ``is_private``
        # existait depuis l'origine, avec son badge dans l'UI, sa contrainte DB
        # (« privée ⇒ non assignée ») et son exclusion du récap — mais **aucun
        # filtre ici**, si bien que la tâche privée d'un membre était servie à tous
        # les autres. Le drapeau était décoratif partout où il comptait le plus.
        #
        # Le filtre vit dans ``get_queryset`` et pas dans une permission objet :
        # une permission ne se prononce que sur un objet déjà chargé, donc elle
        # protège le détail et laisse passer la liste — qui est justement là où on
        # lit les secrets des autres.
        qs = narrow_for(qs, self.request.user)

        zone_id = self.request.query_params.get('zone', '').strip()
        if zone_id:
            qs = qs.filter(zones__id=zone_id).distinct()

        if self.request.query_params.get('overdue') == 'true':
            qs = qs.filter(
                due_date__lt=timezone.now().date()
            ).exclude(status__in=['done', 'archived'])

        due_before = self.request.query_params.get('due_before', '').strip()
        if due_before:
            try:
                due_limit = date.fromisoformat(due_before)
            except ValueError:
                raise ValidationError({'due_before': 'Must be an ISO date (YYYY-MM-DD).'})
            qs = qs.filter(due_date__lte=due_limit)

        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.household:
            ctx['household_id'] = self.request.household.id
        return ctx

    def perform_create(self, serializer):
        zone_ids = serializer.validated_data.get('zone_ids') or []
        # Aucune zone fournie → on attache à la racine du household actif (créée
        # automatiquement à la création du foyer, garantie d'exister).
        if not zone_ids and self.request.household:
            root = Zone.objects.filter(household=self.request.household, parent__isnull=True).first()
            if root is not None:
                zone_ids = [str(root.id)]
                serializer.validated_data['zone_ids'] = zone_ids
        if not zone_ids:
            raise ValidationError({'zone_ids': 'At least one zone is required.'})

        zones = list(
            Zone.objects.for_user_households(self.request.user).filter(id__in=zone_ids)
        )
        if len(zones) != len(zone_ids):
            raise ValidationError({'zone_ids': 'One or more zones are invalid or inaccessible.'})

        household_ids = {str(z.household_id) for z in zones}
        if len(household_ids) != 1:
            raise ValidationError({'zone_ids': 'All zones must belong to the same household.'})

        zone_household_id = next(iter(household_ids))
        if self.request.household and str(self.request.household.id) != zone_household_id:
            raise ValidationError({'household_id': 'Selected household does not match provided zones.'})

        serializer.save(
            household_id=zone_household_id,
            created_by=self.request.user,
        )
        # Prévenir le foyer se fait ici et non dans ``tasks.services.create_task`` :
        # ce service est aussi la porte de ``chickens`` (qui a déjà sa propre
        # notification) et de ``seed_demo_data``. Voir ``tasks/notifications.py``.
        notify_task_created(serializer.instance, self.request.user)

    def _check_update_permission(self, instance, validated_data):
        user = self.request.user
        is_creator = instance.created_by_id == user.pk
        if is_creator:
            return
        is_assignee = instance.assigned_to_id is not None and instance.assigned_to_id == user.pk
        if is_assignee:
            non_status_fields = set(validated_data.keys()) - {'status'}
            if non_status_fields:
                raise PermissionDenied("Assignees can only change the task status.")
            return
        raise PermissionDenied("Only the creator or assignee can modify this task.")

    def perform_update(self, serializer):
        instance = serializer.instance
        self._check_update_permission(instance, serializer.validated_data)
        new_status = serializer.validated_data.get('status')
        kwargs = {'updated_by': self.request.user}

        if new_status == Task.Status.DONE and not instance.completed_at:
            kwargs['completed_at'] = timezone.now()
            kwargs['completed_by'] = self.request.user
        elif new_status and new_status != Task.Status.DONE and instance.completed_at:
            kwargs['completed_at'] = None
            kwargs['completed_by'] = None

        serializer.save(**kwargs)

    def perform_destroy(self, instance):
        from .services import archive_task

        archive_task(self.request.user, instance)


class TaskDocumentViewSet(viewsets.ModelViewSet):
    """CRUD for Task↔Document links."""

    permission_classes = [IsHouseholdMember]
    serializer_class = TaskDocumentLinkSerializer

    def _task_ct(self):
        return ContentType.objects.get_for_model(Task)

    def get_queryset(self):
        task_ids = Task.objects.for_user_households(self.request.user).values_list('id', flat=True)
        qs = DocumentLink.objects.filter(
            content_type=self._task_ct(), object_id__in=task_ids
        ).select_related('document')
        if self.request.household:
            hh_task_ids = Task.objects.filter(
                household=self.request.household
            ).values_list('id', flat=True)
            qs = qs.filter(object_id__in=hh_task_ids)
        task_id = self.request.query_params.get('task', '').strip()
        if task_id:
            qs = qs.filter(object_id=task_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        task = serializer.validated_data['task']
        document = serializer.validated_data['document']
        if not Task.objects.for_user_households(self.request.user).filter(id=task.id).exists():
            raise ValidationError({'task': 'Invalid task or access denied.'})
        if task.created_by_id != self.request.user.pk:
            raise PermissionDenied("Only the task creator can manage attachments.")
        if str(document.household_id) != str(task.household_id):
            raise ValidationError(
                {'document': 'Document must belong to the same household as the task.'}
            )
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        task = instance.entity  # the linked Task (GenericForeignKey)
        if task is None or task.created_by_id != self.request.user.pk:
            raise PermissionDenied("Only the task creator can manage attachments.")
        instance.delete()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = serializer.validated_data['task']
        document = serializer.validated_data['document']
        if DocumentLink.objects.filter(
            content_type=self._task_ct(), object_id=task.id, document=document
        ).exists():
            return Response(
                {'code': 'already_linked', 'detail': 'This document is already linked to this task.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {'code': 'already_linked', 'detail': 'This document is already linked to this task.'},
                status=status.HTTP_409_CONFLICT,
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskInteractionViewSet(viewsets.ModelViewSet):
    """CRUD for Task↔Interaction links."""

    permission_classes = [IsHouseholdMember]
    serializer_class = TaskInteractionLinkSerializer

    def get_queryset(self):
        qs = TaskInteraction.objects.filter(
            task__household_id__in=self.request.user.householdmember_set.values_list(
                'household_id', flat=True
            )
        ).select_related('interaction', 'task')
        if self.request.household:
            qs = qs.filter(task__household=self.request.household)
        task_id = self.request.query_params.get('task', '').strip()
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs

    def perform_create(self, serializer):
        task = serializer.validated_data['task']
        interaction = serializer.validated_data['interaction']
        if not Task.objects.for_user_households(self.request.user).filter(id=task.id).exists():
            raise ValidationError({'task': 'Invalid task or access denied.'})
        if task.created_by_id != self.request.user.pk:
            raise PermissionDenied("Only the task creator can manage attachments.")
        if str(interaction.household_id) != str(task.household_id):
            raise ValidationError(
                {'interaction': 'Interaction must belong to the same household as the task.'}
            )
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.task.created_by_id != self.request.user.pk:
            raise PermissionDenied("Only the task creator can manage attachments.")
        instance.delete()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = serializer.validated_data['task']
        interaction = serializer.validated_data['interaction']
        if TaskInteraction.objects.filter(task=task, interaction=interaction).exists():
            return Response(
                {'code': 'already_linked', 'detail': 'This interaction is already linked to this task.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {'code': 'already_linked', 'detail': 'This interaction is already linked to this task.'},
                status=status.HTTP_409_CONFLICT,
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
