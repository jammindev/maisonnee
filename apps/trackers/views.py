"""
Tracker REST API views.

Entry writes (create/update/destroy) delegate to ``trackers.services`` — the
single write path shared with the agent — so the tracker cache
(``last_value`` / ``last_entry_at`` / ``entries_summary``) is refreshed on
every write.
"""
from django.db.models import Prefetch
from rest_framework import filters, viewsets
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsHouseholdMember
from core.visibility import narrow_for

from . import services
from .models import Tracker, TrackerEntry
from .serializers import TrackerEntrySerializer, TrackerSerializer


class TrackerViewSet(viewsets.ModelViewSet):
    """Tracker CRUD. DELETE archives (``is_active=False``); history is kept."""

    permission_classes = [IsHouseholdMember]
    serializer_class = TrackerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project']
    search_fields = ['name', 'description']
    ordering_fields = ['last_entry_at', 'name', 'created_at']
    ordering = ['-last_entry_at', 'name']

    class Pagination(LimitOffsetPagination):
        default_limit = 200
        max_limit = 500

    pagination_class = Pagination

    def get_queryset(self):
        qs = Tracker.objects.for_user_households(self.request.user).select_related(
            'project', 'created_by'
        ).prefetch_related(
            Prefetch(
                'entries',
                # 120 rows absorb backdated bursts; the serializer trims to 30 points.
                queryset=TrackerEntry.objects.order_by('-occurred_at', '-created_at')[:120],
                to_attr='sparkline_entries',
            )
        )
        if self.request.household:
            qs = qs.filter(household=self.request.household)
        # Un tracker hérite de la confidentialité de son chantier — il n'a pas de
        # drapeau propre. Déclaré dans ``trackers.apps``, appliqué ici comme
        # partout ailleurs.
        qs = narrow_for(qs, self.request.user)

        params = self.request.query_params
        if params.get('include_archived') not in ('1', 'true'):
            qs = qs.filter(is_active=True)
        if params.get('general') == 'true':
            qs = qs.filter(project__isnull=True)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.household:
            ctx['household_id'] = self.request.household.id
        return ctx

    def perform_create(self, serializer):
        serializer.save(household=self.request.household, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.updated_by = self.request.user
        instance.save(update_fields=['is_active', 'updated_by', 'updated_at'])


class TrackerEntryViewSet(viewsets.ModelViewSet):
    """Entry CRUD — all writes flow through ``trackers.services``."""

    permission_classes = [IsHouseholdMember]
    serializer_class = TrackerEntrySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tracker']
    ordering_fields = ['occurred_at', 'created_at']
    ordering = ['-occurred_at', '-created_at']

    class Pagination(LimitOffsetPagination):
        default_limit = 100
        max_limit = 500

    pagination_class = Pagination

    def get_queryset(self):
        qs = TrackerEntry.objects.for_user_households(self.request.user).select_related(
            'tracker'
        )
        if self.request.household:
            qs = qs.filter(household=self.request.household)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.household:
            ctx['household_id'] = self.request.household.id
        return ctx

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.add_entry(
            self.request.household,
            self.request.user,
            data['tracker'],
            value=data['value'],
            occurred_at=data.get('occurred_at'),
            note=data.get('note'),
        )

    def perform_update(self, serializer):
        fields = {
            k: v
            for k, v in serializer.validated_data.items()
            if k in ('value', 'occurred_at', 'note')
        }
        serializer.instance = services.update_entry(
            self.request.household, self.request.user, serializer.instance, fields=fields
        )

    def perform_destroy(self, instance):
        services.delete_entry(self.request.household, self.request.user, instance)
