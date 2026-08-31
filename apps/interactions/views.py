"""
Interaction views for REST API.
"""
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count

from core.permissions import IsHouseholdMember
from core.visibility import narrow_for
from core.timezones import (
    current_month_range,
    end_of_day,
    household_tz,
    start_of_day,
)
from documents.models import Document, DocumentLink
from zones.models import Zone
from .aggregations import UNBUDGETED, compute_expense_summary
from .notifications import notify_note_created, retract_note_created
from .models import (
    Interaction,
    InteractionZone,
    InteractionContact,
    InteractionStructure,
    Supplier,
)
from .serializers import (
    InteractionSerializer,
    InteractionDetailSerializer,
    InteractionContactSerializer,
    InteractionStructureSerializer,
    InteractionDocumentSerializer,
    ManualExpenseSerializer,
    RenovationSerializer,
    RenovationUpdateSerializer,
)
from .services import (
    create_manual_expense_interaction,
    create_renovation_interaction,
    update_renovation_interaction,
)


def _parse_bound(value: str, household, *, closing: bool) -> datetime:
    """Une borne de période, toujours *aware*, toujours dans le fuseau du foyer.

    Deux erreurs qu'un seul endroit ferme désormais :

    - **une date nue en fin d'intervalle vaut fin de journée.** Le filtre est un
      ``__lte`` : lue à minuit, ``to=2026-07-31`` excluait toutes les dépenses du
      31 ;
    - **une date nue se lit chez le foyer, pas en UTC.** Elle était forcée à
      ``tzinfo=utc`` alors que le panneau Budgets bornait son mois sur le fuseau
      du foyer : les deux écrans annonçaient deux totaux pour la même enveloppe,
      chacun juste selon sa propre borne. Le décalage n'est que de deux heures,
      mais il tombe pile sur la frontière d'un mois — donc sur un budget.

    Un instant explicite (``...T14:00``) est respecté ; naïf, il est simplement
    ancré dans le fuseau du foyer plutôt que dans celui du serveur.
    """
    try:
        day = datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        moment = datetime.fromisoformat(value)
        if timezone.is_naive(moment):
            return moment.replace(tzinfo=household_tz(household))
        return moment
    return end_of_day(day, household) if closing else start_of_day(day, household)


#: Ce qu'un drapeau de query string veut dire « oui ». Mêmes valeurs que
#: ``documents.views`` pour ``without_zone``, dont ce filtre est le pendant : deux
#: vocabulaires pour le même drapeau se répondraient différemment sur `?flag=true`.
_TRUTHY_PARAMS = {'1', 'true', 'yes'}


def _is_truthy(value: str | None) -> bool:
    """Vrai si le paramètre dit oui. ``?flag=0`` dit **non**, pas « présent ».

    Un front qui envoie toujours la clé ne doit pas filtrer à son insu.
    """
    return (value or '').lower() in _TRUTHY_PARAMS


def _parse_period(from_param: str | None, to_param: str | None, household):
    """Resolve from/to query params, defaulting to the household's current month.

    Le défaut passe par ``core.timezones`` — la **même** fonction que le panneau
    Budgets. C'est ce qui garantit qu'ouvrir une enveloppe affiche le total sur
    lequel on vient de cliquer.
    """
    if not from_param and not to_param:
        start, end, _month = current_month_range(household)
        # Fin inclusive : le contrat de l'agrégat est un ``__lte``.
        return start, end - timedelta(microseconds=1)

    from_dt = _parse_bound(from_param, household, closing=False) if from_param else None
    to_dt = _parse_bound(to_param, household, closing=True) if to_param else None
    return from_dt, to_dt


class InteractionViewSet(viewsets.ModelViewSet):
    """
    Interaction CRUD with filtering by type, tags, zones, dates.
    """
    permission_classes = [IsHouseholdMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # ⚠️ Pas de ``is_private`` ici — voir la note jumelle de ``TaskViewSet``.
    # Le filtre servait à lire les items privés des autres, et le front ne l'a
    # jamais envoyé. Un filtre ne doit jamais pouvoir élargir ce que borne le
    # queryset, et le queryset le borne désormais (voir ``get_queryset``).
    filterset_fields = ['type', 'created_by']
    search_fields = ['subject', 'content', 'enriched_text', 'tags__tag__name']
    ordering_fields = ['occurred_at', 'created_at', 'subject']
    ordering = ['-occurred_at']

    class Pagination(LimitOffsetPagination):
        default_limit = 8
        max_limit = 100

    pagination_class = Pagination
    
    def get_queryset(self):
        """Filter interactions to households where current user is a member."""
        # ``bank_transaction__account``: the serializer answers « rapprochée ? »
        # and names the operation for the link. Without the join that is two
        # queries per row.
        queryset = Interaction.objects.for_user_households(self.request.user).select_related(
            'created_by', 'budget', 'household', 'bank_transaction__account'
        ).prefetch_related('zones', 'documents', 'source', 'tags__tag')

        selected_household = self.request.household
        if selected_household:
            queryset = queryset.filter(household=selected_household)

        # Confidentialité — une note privée n'appartient qu'à qui l'a écrite.
        #
        # Le scope foyer ci-dessus ne dit rien de la confidentialité. ``is_private``
        # existait sur ce modèle depuis l'origine, avec son exclusion des
        # notifications (``interactions.notifications``) et sa garde dans les
        # services d'édition — mais **aucun filtre ici**, si bien que la note privée
        # d'un membre était servie à tous les autres. Le drapeau était décoratif là
        # où il comptait le plus.
        #
        # Le filtre vit dans ``get_queryset`` et pas dans une permission objet : une
        # permission ne se prononce que sur un objet déjà chargé, donc elle protège
        # le détail et laisse passer la liste — qui est justement là où on lit les
        # secrets des autres.
        #
        # ⚠️ L'exception ``expense`` est délibérée et documentée dans
        # ``interactions.visibility`` : l'argent se **masque** au lot 4, il ne se
        # cache pas, sous peine de donner deux définitions à sept agrégations.
        queryset = narrow_for(queryset, self.request.user)

        # Exclure des types — le pendant de ``?type=``, et il doit être **serveur**.
        #
        # La page Activité ne montre plus les dépenses : elles ont leur module, avec
        # leurs filtres, leur badge de rapprochement et leur budget, et à cent
        # soixante lignes par mois elles noyaient les notes et les maintenances.
        # Filtrer côté client aurait été plus court et faux : la page est paginée par
        # huit, donc une page de huit dépenses se serait affichée vide sous un
        # compteur qui en annonce huit.
        exclude_type = self.request.query_params.get('exclude_type')
        if exclude_type:
            excluded = [value.strip() for value in exclude_type.split(',') if value.strip()]
            if excluded:
                queryset = queryset.exclude(type__in=excluded)

        # « Quelles dépenses déjà saisies pourraient être celle-ci ? » — le vivier
        # du rattachement manuel, dans les deux sens.
        #
        # ⚠️ Volontairement **hors fenêtre de conformité**, contrairement au
        # détecteur `expense_unreconciled` : celui-ci répond « qu'est-ce que je
        # dois réclamer ? », celui-là « qu'est-ce qui existe déjà ? ». Une dépense
        # postérieure au dernier relevé n'est pas un écart, mais elle est
        # exactement celle qu'on vient de saisir et qu'on risque de re-créer en
        # double au moment de ventiler.
        if self.request.query_params.get('unreconciled') == 'true':
            queryset = queryset.filter(type='expense', bank_transaction__isnull=True)

        # Plafond de montant — ce qui tient dans le reste à ventiler d'une ligne.
        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            try:
                queryset = queryset.filter(amount__lte=Decimal(max_amount))
            except (InvalidOperation, TypeError):
                raise ValidationError({'max_amount': 'Expected a decimal amount.'})

        # Filter by zone
        zone_id = self.request.query_params.get('zone')
        if zone_id:
            queryset = queryset.filter(zones__id=zone_id)

        # Filter by polymorphic source (e.g. ?source_type=projects.project&source_id=<uuid>)
        source_type = self.request.query_params.get('source_type')
        if source_type:
            try:
                app_label, model = source_type.strip().lower().split('.')
                source_ct = ContentType.objects.get_by_natural_key(app_label, model)
            except (ValueError, ContentType.DoesNotExist):
                return queryset.none()
            queryset = queryset.filter(source_content_type=source_ct)
        source_id = self.request.query_params.get('source_id')
        if source_id:
            try:
                queryset = queryset.filter(source_object_id=uuid.UUID(source_id))
            except ValueError:
                return queryset.none()

        # Filter by contact
        contact_id = self.request.query_params.get('contact')
        if contact_id:
            queryset = queryset.filter(interaction_contacts__contact_id=contact_id)

        # Filter by structure
        structure_id = self.request.query_params.get('structure')
        if structure_id:
            queryset = queryset.filter(interaction_structures__structure_id=structure_id)

        # Filter by date range — **les mêmes bornes que le résumé**, via
        # ``_parse_bound``. La liste et le total affichés côte à côte sur la page
        # d'un budget doivent compter les mêmes dépenses ; comparer une chaîne
        # brute les faisait lire minuit UTC là où l'agrégat lisait le fuseau du
        # foyer.
        household_for_dates = self.request.household
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(
                occurred_at__gte=_parse_bound(start_date, household_for_dates, closing=False)
            )
        if end_date:
            queryset = queryset.filter(
                occurred_at__lte=_parse_bound(end_date, household_for_dates, closing=True)
            )
        
        # Filter by tags
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = tags.split(',')
            queryset = queryset.filter(tags__tag__name__in=tag_list).distinct()

        # Filter by kind — generic across interaction subtypes. Expense kinds
        # live in the promoted `kind` column; non-expense subtypes (e.g.
        # renovation) keep their discriminator in metadata. Match either so this
        # shared list endpoint filters every subtype uniformly.
        kind = self.request.query_params.get('kind')
        if kind:
            queryset = queryset.filter(Q(kind=kind) | Q(metadata__kind=kind))

        # Filter by supplier (expense-only, now a real column).
        supplier = self.request.query_params.get('supplier')
        if supplier is not None:
            queryset = queryset.filter(supplier=supplier)

        # « Celles auxquelles il manque un fournisseur » — le pendant en liste de la
        # pastille, et ce qui permet de composer une sélection à corriger en masse.
        #
        # Un paramètre à part et non une valeur de ``supplier`` : un fournisseur
        # pourrait s'appeler « none », et la chaîne vide est déjà lue juste au-dessus
        # comme un filtre — donc indistinguable, côté client, de l'absence de filtre.
        if _is_truthy(self.request.query_params.get('without_supplier')):
            queryset = queryset.filter(supplier__regex=r'^\s*$')

        # Filter by budget — « de quoi ce compteur est-il fait ? ».
        #
        # ``budget=none`` est une valeur à part entière, pas l'absence de filtre :
        # « hors budget » est un seau qu'on veut pouvoir ouvrir comme les autres.
        # Sans elle, la seule façon de lister ses dépenses serait de tout charger
        # et de filtrer côté client.
        budget = self.request.query_params.get('budget')
        if budget:
            if budget == UNBUDGETED:
                queryset = queryset.filter(budget__isnull=True)
            else:
                try:
                    queryset = queryset.filter(budget_id=uuid.UUID(budget))
                except ValueError:
                    # Un id malformé ne doit pas renvoyer *tout* le journal : la
                    # liste vide est le seul résultat honnête.
                    return queryset.none()

        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InteractionDetailSerializer
        return InteractionSerializer
    
    def perform_create(self, serializer):
        """Set household and created_by with legacy RLS-style validation."""
        zone_ids = self.request.data.get('zone_ids') or []
        document_ids = self.request.data.get('document_ids') or []
        if not isinstance(zone_ids, list) or not zone_ids:
            raise ValidationError({'zone_ids': 'At least one zone is required.'})
        if not isinstance(document_ids, list):
            raise ValidationError({'document_ids': 'Documents must be provided as a list.'})

        zones = list(
            Zone.objects.for_user_households(self.request.user).filter(id__in=zone_ids)
        )

        if len(zones) != len(zone_ids):
            raise ValidationError({'zone_ids': 'One or more zones are invalid or inaccessible.'})

        household_ids = {str(zone.household_id) for zone in zones}
        if len(household_ids) != 1:
            raise ValidationError({'zone_ids': 'All zones must belong to the same household.'})

        zone_household_id = next(iter(household_ids))
        selected_household = self.request.household
        if selected_household and str(selected_household.id) != zone_household_id:
            raise ValidationError({'household_id': 'Selected household does not match provided zones.'})

        documents = list(
            Document.objects.filter(
                household_id__in=self.request.user.householdmember_set.values_list('household_id', flat=True),
                id__in=document_ids,
            )
        )
        if len(documents) != len(document_ids):
            raise ValidationError({'document_ids': 'One or more documents are invalid or inaccessible.'})
        if any(str(document.household_id) != zone_household_id for document in documents):
            raise ValidationError({'document_ids': 'All documents must belong to the same household as the selected zones.'})

        serializer.save(
            household_id=zone_household_id,
            created_by=self.request.user,
        )
        # Seules les **notes** sonnent : cet endpoint sert les onze types du
        # journal, et notifier sur l'ensemble ferait sonner chaque achat de stock
        # et chaque ligne de relevé ventilée. La garde de type vit dans
        # ``notify_note_created``, pas ici — voir ``interactions/notifications.py``.
        notify_note_created(serializer.instance, self.request.user)

    def perform_destroy(self, instance):
        """Supprimer l'objet **et** ce qui l'annonçait.

        Une note supprimée laisse sinon dans la cloche des autres membres un lien
        vers un écran mort. Le retrait passe par l'id, pas par l'instance : la
        ligne est sur le point de disparaître.
        """
        note_id = instance.id if instance.type == 'note' else None
        super().perform_destroy(instance)
        if note_id is not None:
            retract_note_created(note_id)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Group interactions by type with counts."""
        queryset = self.get_queryset()
        type_counts = {}
        
        for int_type, label in Interaction.INTERACTION_TYPES:
            count = queryset.filter(type=int_type).count()
            if count > 0:
                type_counts[int_type] = {
                    'label': label,
                    'count': count
                }
        
        return Response(type_counts)

    @action(detail=False, methods=['post'], url_path='expenses/manual')
    def expenses_manual(self, request):
        """POST /api/interactions/expenses/manual/

        Create an Interaction(type=expense) NOT linked to a domain object —
        the user-typed `subject` is what gets stored. Used for ad-hoc expenses
        (restaurant, cinema, gift…).
        """
        household = request.household
        if household is None:
            raise ValidationError({"household_id": "A valid household context is required."})

        serializer = ManualExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            interaction = create_manual_expense_interaction(
                household=household,
                user=request.user,
                subject=serializer.validated_data["subject"],
                amount=serializer.validated_data.get("amount"),
                supplier=serializer.validated_data.get("supplier", "") or "",
                occurred_at=serializer.validated_data.get("occurred_at"),
                notes=serializer.validated_data.get("notes", "") or "",
                zone_ids=serializer.validated_data.get("zone_ids") or None,
                budget_id=serializer.validated_data.get("budget_id"),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        payload = InteractionSerializer(interaction, context={"request": request}).data
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='renovation')
    def renovation_create(self, request):
        """POST /api/interactions/renovation/

        Create a renovation/decoration log entry (parcours 13): an Interaction
        discriminated by metadata.kind="renovation", attachable to several zones
        at once. Delegates to interactions.services.create_renovation_interaction.
        """
        household = request.household
        if household is None:
            raise ValidationError({"household_id": "A valid household context is required."})

        serializer = RenovationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            interaction = create_renovation_interaction(
                household=household,
                user=request.user,
                element=data["element"],
                product=data.get("product", "") or "",
                brand=data.get("brand", "") or "",
                reference=data.get("reference", "") or "",
                interaction_type=data.get("interaction_type", "installation"),
                subject=data.get("subject") or None,
                occurred_at=data.get("occurred_at"),
                notes=data.get("notes", "") or "",
                zone_ids=data["zone_ids"],
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        payload = InteractionSerializer(interaction, context={"request": request}).data
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='renovation')
    def renovation_update(self, request, pk=None):
        """PATCH /api/interactions/{id}/renovation/

        Edit a renovation log entry via the shared service. Every field optional;
        zone_ids resyncs the M2M when provided.
        """
        interaction = self.get_object()
        household = request.household or interaction.household

        serializer = RenovationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        fields = {
            key: data[key]
            for key in ("element", "product", "brand", "reference",
                        "interaction_type", "subject", "notes", "occurred_at")
            if key in data
        }

        try:
            interaction = update_renovation_interaction(
                household=household,
                user=request.user,
                interaction=interaction,
                fields=fields,
                zone_ids=data.get("zone_ids"),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        payload = InteractionSerializer(interaction, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk-update')
    def bulk_update(self, request):
        """POST /api/interactions/interactions/bulk-update/ — corriger un lot de dépenses.

        Body : ``{"ids": [...], "supplier": "…", "budget_id": "…"|null}``. Les deux
        champs sont optionnels **mais pas simultanément** : une requête qui
        n'exprime aucune intention ne peut pas répondre « 12 mises à jour ».

        Le lot est **atomique**. Un id inconnu, hors du foyer, ou qui n'est pas une
        dépense fait échouer l'ensemble : écrire les huit ids valides en taisant
        les quatre autres laisserait celui qui a lancé le lot sans moyen de savoir
        ce qui a été fait, et aucun écran ne rattrape une écriture partielle.

        Et il applique **les mêmes règles que l'écriture unitaire** — catalogue de
        fournisseurs, refus du budget global ou d'un autre foyer. Un chemin de
        masse qui contournerait les validations du chemin unitaire serait une porte
        ouverte sur des données que rien n'a vérifiées.
        """
        from .services import _resolve_expense_budget, register_supplier

        household = request.household
        if household is None:
            raise ValidationError({'detail': 'No household selected.'})

        raw_ids = request.data.get('ids')
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValidationError({'ids': 'Expected a non-empty list of interaction ids.'})

        try:
            ids = [uuid.UUID(str(value)) for value in raw_ids]
        except (ValueError, AttributeError, TypeError):
            # Un id malformé atteindrait le driver comme un crash : un mauvais
            # paramètre est un 400, jamais un 500.
            raise ValidationError({'ids': 'One or more ids are not valid uuids.'})

        has_supplier = 'supplier' in request.data
        has_budget = 'budget_id' in request.data
        if not has_supplier and not has_budget:
            raise ValidationError(
                {'detail': 'Nothing to change: provide "supplier" and/or "budget_id".'}
            )

        # Le comptage se fait sur un `set` : une sélection qui répète un id ne doit
        # pas gonfler le total annoncé.
        unique_ids = set(ids)
        rows = list(
            Interaction.objects.filter(
                id__in=unique_ids, household_id=household.id, type='expense'
            ).values_list('id', flat=True)
        )
        if len(rows) != len(unique_ids):
            missing = len(unique_ids) - len(rows)
            raise ValidationError({
                'ids': (
                    f'{missing} of {len(unique_ids)} entries are not expenses of this '
                    f'household; nothing was changed.'
                )
            })

        changes = {'updated_by': request.user, 'updated_at': timezone.now()}
        canonical_supplier = None
        if has_supplier:
            canonical_supplier = register_supplier(
                household_id=household.id, user=request.user, name=request.data['supplier']
            )
            changes['supplier'] = canonical_supplier
        if has_budget:
            # `null` est un choix (« retirer l'enveloppe ») ; l'absence de clé est
            # « ne touche pas au budget ». Les confondre rendrait l'un des deux
            # gestes impossible.
            try:
                changes['budget'] = _resolve_expense_budget(
                    household.id, request.data['budget_id']
                )
            except ValueError as exc:
                raise ValidationError({'budget_id': str(exc)})

        # `.update()` et non une boucle de `save()` : c'est une seule requête, et
        # elle est indivisible. Le revers est qu'elle contourne `save()`, d'où
        # `updated_by`/`updated_at` posés à la main — une écriture de masse sans
        # trace est précisément celle qu'on voudra relire.
        Interaction.objects.filter(id__in=rows).update(**changes)

        return Response({
            'updated': len(rows),
            'supplier': canonical_supplier,
        })

    @action(detail=False, methods=['get'], url_path='suppliers')
    def suppliers(self, request):
        """GET /api/interactions/suppliers/ — le catalogue des fournisseurs du foyer.

        La table `Supplier`, dans l'ordre où elle sert : **le plus employé
        d'abord**. Un tri alphabétique remettrait le magasin des courses
        hebdomadaires derrière un achat unique d'il y a deux ans, ce qui rend le
        select aussi lent à parcourir que le champ libre qu'il remplace.

        Le compte se calcule ici, en un `GROUP BY` sur la colonne texte, et n'est
        **pas** dénormalisé sur la table : un compteur stocké est un compteur à
        deux définitions dès la première suppression de dépense — même règle que le
        « dépensé » d'un budget. Un fournisseur au catalogue mais jamais employé
        (créé, puis la dépense annulée) sort avec `count: 0` et passe après les
        autres ; il reste proposé, parce que l'avoir tapé une fois est déjà un
        signe qu'on le retapera.

        Pas de pagination ni de recherche serveur : le filtrage se fait à la frappe
        côté client, et un foyer compte ses fournisseurs en dizaines. Un
        aller-retour par caractère coûterait plus cher que la liste entière.
        """
        household = request.household
        if household is None:
            return Response({'results': []})

        counts = dict(
            Interaction.objects
            .filter(household_id=household.id)
            .exclude(supplier='')
            .values_list('supplier')
            .annotate(total=Count('id'))
        )
        rows = [
            {'name': name, 'count': counts.get(name, 0)}
            for name in Supplier.objects
            .filter(household_id=household.id)
            .values_list('name', flat=True)
        ]
        rows.sort(key=lambda row: (-row['count'], row['name'].casefold()))
        return Response({'results': rows})

    @action(detail=False, methods=['get'], url_path='expenses/summary')
    def expenses_summary(self, request):
        """GET /api/interactions/expenses/summary/?from=&to=&supplier=&kind=

        Aggregates expense interactions for the selected household over a
        period. Defaults to the current calendar month when from/to are omitted.
        """
        household = request.household
        if household is None:
            return Response({
                'period': {'from': None, 'to': None},
                'total': '0.00',
                'count': 0,
                'by_kind': [],
                'by_supplier': [],
                'by_month': [],
            })

        from_dt, to_dt = _parse_period(
            request.query_params.get('from'),
            request.query_params.get('to'),
            household,
        )
        supplier = request.query_params.get('supplier')
        kind = request.query_params.get('kind')

        budget = request.query_params.get('budget') or None
        if budget and budget != UNBUDGETED:
            try:
                uuid.UUID(budget)
            except ValueError:
                # Un id malformé atteint le driver comme un crash, pas comme un
                # filtre : un mauvais paramètre est un 400, jamais un 500.
                raise ValidationError({'budget': 'Expected a budget id or "none".'})

        return Response(compute_expense_summary(
            household_id=household.id,
            from_dt=from_dt,
            to_dt=to_dt,
            supplier=supplier if supplier else None,
            kind=kind if kind else None,
            budget=budget,
            # Le même filtre que la liste, et pas par confort : les cartes de total
            # sont affichées **au-dessus** d'elle. Un compteur qui compte des lignes
            # que la liste ne montre pas fait perdre leur crédit aux deux, et aucun
            # ne dit lequel se trompe.
            without_supplier=_is_truthy(request.query_params.get('without_supplier')),
        ))


class _InteractionLinkBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsHouseholdMember]

    def get_queryset(self):
        queryset = self.model.objects.filter(
            interaction__household_id__in=self.request.user.householdmember_set.values_list('household_id', flat=True)
        )
        selected_household = self.request.household
        if selected_household:
            queryset = queryset.filter(interaction__household=selected_household)
        return queryset

    def perform_create(self, serializer):
        interaction = serializer.validated_data.get('interaction')
        if not Interaction.objects.for_user_households(self.request.user).filter(id=interaction.id).exists():
            raise ValidationError({'interaction': 'Invalid interaction or access denied.'})
        serializer.save()


class InteractionContactViewSet(_InteractionLinkBaseViewSet):
    model = InteractionContact
    serializer_class = InteractionContactSerializer


class InteractionStructureViewSet(_InteractionLinkBaseViewSet):
    model = InteractionStructure
    serializer_class = InteractionStructureSerializer


class InteractionDocumentViewSet(_InteractionLinkBaseViewSet):
    """Interaction↔Document links, backed by the polymorphic DocumentLink."""
    serializer_class = InteractionDocumentSerializer

    def _interaction_ct(self):
        return ContentType.objects.get_for_model(Interaction)

    def get_queryset(self):
        int_ids = Interaction.objects.for_user_households(self.request.user).values_list('id', flat=True)
        qs = DocumentLink.objects.filter(
            content_type=self._interaction_ct(), object_id__in=int_ids
        ).select_related('document')
        if self.request.household:
            hh_ids = Interaction.objects.filter(
                household=self.request.household
            ).values_list('id', flat=True)
            qs = qs.filter(object_id__in=hh_ids)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        interaction = serializer.validated_data.get('interaction')
        if not Interaction.objects.for_user_households(self.request.user).filter(id=interaction.id).exists():
            raise ValidationError({'interaction': 'Invalid interaction or access denied.'})
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        interaction = serializer.validated_data['interaction']
        document = serializer.validated_data['document']
        if DocumentLink.objects.filter(
            content_type=self._interaction_ct(), object_id=interaction.id, document=document
        ).exists():
            return Response(
                {
                    'code': 'already_linked',
                    'detail': 'Exact document-interaction link already exists.',
                },
                status=status.HTTP_409_CONFLICT,
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
