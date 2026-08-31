"""Document views for REST API."""
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsHouseholdMember
from core.file_validation import validate_upload, ALLOWED_DOCUMENT_TYPES, DOCUMENT_MAX_SIZE
from core.visibility import narrow_for
from .extraction import extract_text
from .exif import read_taken_at
from .image_processing import normalize_image
from .models import Document, DocumentLink
from .queries import (
    TRIAGE_CLUSTERS,
    TRIAGE_WINDOW,
    UNTRIAGED,
    cluster_sessions,
    untriaged,
)
from .queries import purpose_counts as compute_purpose_counts
from .serializers import (
    DocumentSerializer,
    DocumentDetailSerializer,
    DocumentUploadSerializer,
)
from .thumbnails import generate_thumbnails
from .services import (
    add_documents_zones,
    link_document,
    parse_zone_ids,
    set_document_zones,
    zones_of_household,
)
from interactions.models import Interaction
from zones.models import Zone

from .throttles import DocumentUploadThrottle, OcrReprocessThrottle

logger = logging.getLogger(__name__)


def _run_extraction(document: Document, *, feature: str = "ocr_upload", user=None) -> None:
    """Extract text and persist it on the document, fail-soft."""
    try:
        text, method = extract_text(document, feature=feature, user=user)
    except Exception as exc:
        logger.warning("extract_text raised for document %s: %s", document.pk, exc)
        text, method = "", "skipped"

    document.ocr_text = text or ""
    metadata = dict(document.metadata or {})
    metadata["ocr_extracted_at"] = timezone.now().isoformat()
    metadata["ocr_method"] = method
    document.metadata = metadata
    document.save(update_fields=["ocr_text", "metadata", "updated_at"])


#: Types searchables dont le nom est déjà pris par un autre filtre de cet
#: endpoint — ils ne se filtrent donc que par la forme générique `linked_to`.
#: `interaction` est un `filterset_fields` sur la FK `Document.interaction`.
_PARAMS_RESERVED_BY_ANOTHER_FILTER = frozenset({'interaction'})


def get_documents_queryset_for_request(request):
    query_params = getattr(request, 'query_params', request.GET)
    # La restriction passe par le point d'application unique, jamais par un ``Q``
    # réécrit ici : la liste, la permission objet et le retrieval de l'agent ne
    # peuvent pas donner trois réponses s'ils lisent la même déclaration.
    queryset = narrow_for(
        Document.objects.filter(
            household_id__in=request.user.householdmember_set.values_list('household_id', flat=True)
        ),
        request.user,
    ).select_related(
        'created_by',
        'interaction',
    ).prefetch_related(
        Prefetch(
            'links',
            # `entity` est une `GenericForeignKey` : sans ce prefetch imbriqué, chaque
            # lien tire sa cible à part. La liste n'étant pas paginée, sérialiser
            # `zone_links` coûterait alors une requête par lien — cinq cents pour une
            # galerie de cinq cents photos rangées.
            queryset=DocumentLink.objects.select_related('content_type')
            .prefetch_related('entity')
            .order_by('-created_at'),
            to_attr='prefetched_links',
        ),
    )

    selected_household = request.household
    if selected_household:
        queryset = queryset.filter(household=selected_household)

    # All entity links now live in the polymorphic DocumentLink table.
    interaction_ct = ContentType.objects.get_for_model(Interaction)

    qualification_state = (query_params.get('qualification_state') or '').strip()
    without_activity = (query_params.get('without_activity') or '').strip().lower()
    if qualification_state == 'without_activity' or without_activity in {'1', 'true', 'yes'}:
        # No linked interaction = not qualified by an activity.
        queryset = queryset.exclude(links__content_type=interaction_ct)

    # Photos non rangées : aucun lien vers une zone. C'est le pendant en lecture de
    # la pastille « Sans zone » de la galerie — le front ne le déduit pas d'un champ
    # local, sinon filtrer et signaler pourraient se contredire.
    without_zone = (query_params.get('without_zone') or '').strip().lower()
    if without_zone in {'1', 'true', 'yes'}:
        zone_ct = ContentType.objects.get_for_model(Zone)
        queryset = queryset.exclude(links__content_type=zone_ct)

    # L'intention d'une photo. `untriaged` est un **marqueur explicite** : un paramètre
    # vide ou inconnu est refusé, jamais dégradé en « toutes ». Laisser un vide vouloir
    # dire « tous » est ce qui rend un compteur aveugle — l'écran annoncerait « rien à
    # trier » en montrant la galerie entière.
    if 'purpose' in query_params:
        purpose = (query_params.get('purpose') or '').strip()
        if purpose == UNTRIAGED:
            queryset = untriaged(queryset)
        elif purpose in {value for value, _label in Document.Purpose.choices}:
            queryset = queryset.filter(purpose=purpose)
        else:
            raise ValidationError({
                'purpose': (
                    f'Unknown purpose: {purpose!r}. '
                    f'Expected one of technical, observation, memory, {UNTRIAGED}.'
                )
            })

    # Deux formes pour le même filtre : les raccourcis historiques
    # (`?zone=` / `?project=`…) et la forme générique `?linked_to=<type>:<uuid>`.
    #
    # ⚠️ **La liste des raccourcis dérive du registre**, elle n'est plus écrite en
    # dur. Une liste figée (`zone, project, equipment, task, chicken`) ignorait en
    # silence tout type ajouté depuis — et un filtre ignoré ne rend pas *moins* de
    # documents, il les rend **tous**. L'onglet Documents du verger montrait ainsi
    # la photothèque entière du foyer. C'est le pendant de la règle des photos :
    # « un paramètre oublié ne doit pas pouvoir se lire comme un filtre ».
    #
    # `interaction` est la seule exception, et elle est structurelle : c'est déjà
    # un `filterset_fields` sur la FK `Document.interaction`. Un paramètre ne peut
    # pas porter deux sens, donc ce type-là ne se filtre que par `linked_to`.
    from agent import searchables

    entity_filters = []
    for spec in searchables.REGISTRY:
        if spec.entity_type in _PARAMS_RESERVED_BY_ANOTHER_FILTER:
            continue
        value = (query_params.get(spec.entity_type) or '').strip()
        if value:
            entity_filters.append((spec.entity_type, value))

    linked_to = (query_params.get('linked_to') or '').strip()
    if linked_to:
        etype, _, oid = linked_to.partition(':')
        etype, oid = etype.strip(), oid.strip()
        if not etype or not oid:
            raise ValidationError({
                'linked_to': 'Expected the form <entity_type>:<uuid>.'
            })
        entity_filters.append((etype, oid))

    for entity_type, object_id in entity_filters:
        spec = searchables.find_spec(entity_type)
        if spec is None:
            # Ne jamais retomber sur « pas de filtre » : demander les documents
            # d'une entité qu'on ne sait pas résoudre doit **refuser**, pas
            # répondre « tous ». Un silence ici sur-partage.
            raise ValidationError({
                'linked_to': f'Unknown entity type: {entity_type!r}.'
            })
        ct = ContentType.objects.get_for_model(spec.model)
        queryset = queryset.filter(links__content_type=ct, links__object_id=object_id)

    return queryset.distinct()


def get_recent_interaction_candidates(request, household, *, document_id=None, limit=5):
    if household is None:
        return []

    queryset = Interaction.objects.for_user_households(request.user).filter(household=household)
    if document_id:
        # Exclude interactions already linked to this document (via DocumentLink).
        queryset = queryset.exclude(document_links__document_id=document_id)
    queryset = queryset.order_by('-occurred_at')[:limit]
    return [
        {
            'id': str(item.id),
            'subject': item.subject,
            'type': item.type,
            'occurred_at': item.occurred_at,
        }
        for item in queryset
    ]


class DocumentViewSet(viewsets.ModelViewSet):
    """
    Document CRUD with filtering by type, interaction, and search.
    """
    permission_classes = [IsHouseholdMember]
    #: Le seul geste qu'un jeton d'appareil peut atteindre — envoyer. Tout le reste
    #: du viewset (liste, détail, suppression) lui est refusé par défaut, voir
    #: ``core.middleware.DeviceTokenScopeMiddleware``.
    allows_device_token = ('upload',)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'interaction', 'created_by']
    search_fields = ['name', 'notes', 'ocr_text']
    ordering_fields = ['created_at', 'name', 'type', 'taken_at', 'effective_date']
    ordering = ['-created_at']

    def get_throttles(self):
        """L'envoi et la relance d'OCR ont leur propre cap — voir `throttles.py`.

        Le plancher global suffirait à arrêter une boucle, mais pas à borner une
        **facture** : il compte des requêtes, or ici toutes ne coûtent pas la
        même chose. Un envoi vaut un appel de vision ; une lecture ne vaut rien.
        """
        if self.action == 'upload':
            return [DocumentUploadThrottle()]
        if self.action == 'reprocess_ocr':
            return [OcrReprocessThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        """Filter documents to households where current user is a member.

        Annote `effective_date` = `COALESCE(taken_at, created_at)` : la date de prise
        de vue quand on la connaît, celle d'ajout sinon. C'est l'ordre que veut une
        galerie, et il doit se calculer **en SQL** — trier en Python obligerait à
        charger tout le foyer pour afficher une page.

        L'annotation ne remplace pas `taken_at` dans le payload : le front doit pouvoir
        dire « prise le » plutôt que « ajoutée le », donc il lui faut savoir laquelle
        des deux valeurs a servi.
        """
        return get_documents_queryset_for_request(self.request).annotate(
            effective_date=Coalesce('taken_at', 'created_at'),
        )
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer

    def perform_update(self, serializer):
        """Only the document owner can toggle is_private."""
        if 'is_private' in serializer.validated_data:
            document = self.get_object()
            if document.created_by != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only the document owner can change its privacy.")
        serializer.save()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # When the list is scoped to one linked entity, expose which entity so the
        # serializer can surface each document's phase for that context.
        qp = getattr(self.request, 'query_params', self.request.GET)
        entity_id = ''
        for param in ('zone', 'project', 'equipment'):
            entity_id = (qp.get(param) or '').strip()
            if entity_id:
                break
        if not entity_id:
            linked_to = (qp.get('linked_to') or '').strip()
            if ':' in linked_to:
                entity_id = linked_to.split(':', 1)[1].strip()
        if entity_id:
            context['link_entity_id'] = entity_id
        if self.action == 'retrieve':
            document = getattr(self, '_cached_document', None)
            if document is None:
                document = self.get_object()
                self._cached_document = document
            context['recent_interaction_candidates'] = get_recent_interaction_candidates(
                self.request,
                document.household,
                document_id=document.id,
            )
        return context

    def get_object(self):
        if hasattr(self, '_cached_document'):
            return self._cached_document
        self._cached_document = super().get_object()
        return self._cached_document
    
    def perform_create(self, serializer):
        """Set household and created_by with household consistency checks."""
        selected_household = self.request.household
        interaction_id = self.request.data.get('interaction')
        interaction = None

        if interaction_id:
            interaction = Interaction.objects.for_user_households(self.request.user).filter(id=interaction_id).first()
            if not interaction:
                raise ValidationError({'interaction': 'Invalid interaction or access denied.'})

        if selected_household and interaction and interaction.household_id != selected_household.id:
            raise ValidationError({'household_id': 'Selected household does not match interaction household.'})

        household = selected_household or (interaction.household if interaction else None)
        if household is None:
            raise ValidationError({'household_id': 'A valid household context is required.'})

        serializer.save(
            household=household,
            interaction=interaction,
            created_by=self.request.user,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='upload',
        url_name='upload',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        household = request.household
        if household is None:
            raise ValidationError({'household_id': 'A valid household context is required.'})

        uploaded_file = serializer.validated_data['file']
        detected_mime = validate_upload(
            uploaded_file,
            allowed_types=ALLOWED_DOCUMENT_TYPES,
            max_size=DOCUMENT_MAX_SIZE,
            field_name='file',
        )

        zone = None
        zone_id = serializer.validated_data.get('zone')
        if zone_id:
            zone = Zone.objects.filter(id=zone_id, household=household).first()
            if zone is None:
                raise ValidationError({'zone': 'Invalid zone or access denied.'})

        original_name = Path(uploaded_file.name).name or 'Document'

        # AVANT `normalize_image`, qui ré-encode sans transmettre l'EXIF et détruit donc
        # la date de prise de vue — pour tout HEIC/HEIF et pour tout ce qui dépasse
        # `MAX_DIMENSION`, soit l'essentiel des photos réelles. Inverser ces deux lignes
        # rendrait `taken_at` vide sans qu'aucun test d'upload ne s'en aperçoive.
        taken_at = read_taken_at(uploaded_file, household=household)

        try:
            normalized_file, final_mime, normalize_info = normalize_image(uploaded_file, detected_mime)
        except Exception as exc:
            logger.warning("normalize_image failed for %s: %s", original_name, exc)
            normalized_file, final_mime, normalize_info = uploaded_file, detected_mime, {}

        storage_filename = getattr(normalized_file, 'name', uploaded_file.name) or uploaded_file.name
        storage_path = Document.build_upload_path(
            household_id=household.id,
            filename=storage_filename,
        )
        saved_path = default_storage.save(storage_path, normalized_file)
        stored_size = default_storage.size(saved_path) if default_storage.exists(saved_path) else uploaded_file.size

        try:
            with transaction.atomic():
                metadata = {
                    'size': stored_size,
                    'original_filename': original_name,
                }
                if normalize_info.get('transcoded'):
                    metadata['original_mime_type'] = normalize_info.get('original_mime_type')
                    metadata['normalized'] = True
                if normalize_info.get('resized'):
                    metadata['resized'] = True
                if normalize_info.get('final_dimensions'):
                    metadata['dimensions'] = normalize_info['final_dimensions']

                doc_type = serializer.validated_data.get('type') or 'document'
                document = Document.objects.create(
                    household=household,
                    created_by=request.user,
                    file_path=saved_path,
                    name=(serializer.validated_data.get('name') or original_name)[:255],
                    mime_type=final_mime,
                    type=doc_type,
                    is_private=serializer.validated_data.get('is_private', False),
                    notes=serializer.validated_data.get('notes', ''),
                    metadata=metadata,
                    taken_at=taken_at,
                )
                if zone is not None:
                    link_document(
                        entity=zone,
                        document=document,
                        role='photo' if doc_type == 'photo' else 'document',
                        user=request.user,
                    )
        except Exception:
            if default_storage.exists(saved_path):
                default_storage.delete(saved_path)
            raise

        if document.type == 'photo':
            generate_thumbnails(document)
        else:
            _run_extraction(document, feature="ocr_upload", user=request.user)

        # Ce qui revient est borné comme ce qu'on peut appeler : les candidats du
        # journal servent à l'interface web (parcours 02), pas à un appareil. Les
        # renvoyer à un raccourci lui livrerait les libellés des dernières dépenses
        # bancaires en réponse à un envoi de photo.
        from_device = getattr(request, 'device_token', None) is not None
        recent_candidates = [] if from_device else get_recent_interaction_candidates(request, household)
        response_payload = {
            'document': DocumentDetailSerializer(
                document,
                context={
                    'request': request,
                    'recent_interaction_candidates': recent_candidates,
                },
            ).data,
            'detail_url': f'/app/documents/{document.id}/',
        }

        return Response(response_payload, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Group documents by type with counts."""
        queryset = self.get_queryset()
        type_counts = {}
        
        for doc_type, label in Document.DOCUMENT_TYPES:
            count = queryset.filter(type=doc_type).count()
            if count > 0:
                type_counts[doc_type] = {
                    'label': label,
                    'count': count
                }
        
        return Response(type_counts)
    
    @action(detail=True, methods=['post'], url_path='set_zones')
    def set_zones(self, request, pk=None):
        """Remplace les zones d'un document : `{"zone_ids": [...]}`.

        Un seul appel, et non `detach(ancienne)` + `attach(nouvelle)` enchaînés par le
        client : ranger une photo passerait par un état intermédiaire sans zone, et le
        client devrait connaître les anciens liens pour les défaire.

        Une liste vide **efface** les zones — c'est un geste explicite, jamais l'effet
        de bord d'un enregistrement.
        """
        document = self.get_object()

        raw = request.data.get('zone_ids', None)
        if raw is None:
            raise ValidationError({'zone_ids': 'zone_ids is required.'})

        try:
            requested = parse_zone_ids(raw)
            zones = zones_of_household(
                household_id=document.household_id, zone_ids=requested
            )
        except ValueError as error:
            raise ValidationError({'zone_ids': str(error)})

        with transaction.atomic():
            set_document_zones(document=document, zones=zones, user=request.user)

        document = self.get_queryset().get(pk=document.pk)
        serializer = DocumentSerializer(document, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk_add_zones')
    def bulk_add_zones(self, request):
        """Ajoute des zones à un lot de documents : `{document_ids, zone_ids}`.

        **Le lot ajoute, il n'écrase pas** — voir `services.add_documents_zones`.
        Une liste de zones vide est donc refusée : ce serait une destruction de masse
        déguisée en raccourci, et le geste unitaire existe pour ça.

        **Tout ou rien** : un document invisible (autre foyer, privé d'un autre
        membre) refuse le lot entier. En ranger la moitié sans le dire laisserait
        l'utilisateur croire son tri fait.
        """
        raw_documents = request.data.get('document_ids', None)
        raw_zones = request.data.get('zone_ids', None)
        if raw_documents is None:
            raise ValidationError({'document_ids': 'document_ids is required.'})
        if raw_zones is None:
            raise ValidationError({'zone_ids': 'zone_ids is required.'})
        if isinstance(raw_documents, str) or not isinstance(raw_documents, (list, tuple)):
            raise ValidationError({'document_ids': 'document_ids must be a list.'})

        document_ids = []
        for value in raw_documents:
            text = str(value).strip()
            if not text:
                continue
            if not text.isdigit():
                raise ValidationError({'document_ids': f'Invalid document id: {text}'})
            document_ids.append(int(text))
        document_ids = list(dict.fromkeys(document_ids))
        if not document_ids:
            raise ValidationError({'document_ids': 'document_ids cannot be empty.'})

        # `get_queryset()` porte déjà le scope foyer **et** la confidentialité : on ne
        # refait pas ce filtrage ici, sous peine de le voir dériver.
        documents = list(self.get_queryset().filter(pk__in=document_ids))
        if len(documents) != len(document_ids):
            raise ValidationError({'document_ids': 'Invalid document or access denied.'})

        households = {document.household_id for document in documents}
        if len(households) > 1:
            raise ValidationError({'document_ids': 'All documents must share one household.'})

        try:
            requested = parse_zone_ids(raw_zones)
            if not requested:
                raise ValueError('zone_ids cannot be empty.')
            zones = zones_of_household(
                household_id=households.pop(), zone_ids=requested
            )
        except ValueError as error:
            raise ValidationError({'zone_ids': str(error)})

        with transaction.atomic():
            updated = add_documents_zones(
                documents=documents, zones=zones, user=request.user
            )

        return Response({'updated': updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='purpose_counts')
    def purpose_counts(self, request):
        """Combien de photos par intention, dont « à trier ».

        Un endpoint à part, et pas un bloc de la réponse de `triage/` : la galerie
        affiche ces compteurs en permanence, et les obtenir en chargeant une fenêtre de
        photos ferait payer un écran de lecture au prix d'un écran de tri. C'est la
        même exigence que les badges du Contrôle — un compteur reste un `COUNT(*)`.
        """
        return Response(
            compute_purpose_counts(self.get_queryset()), status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def triage(self, request):
        """Les photos que personne n'a rangées, **par grappes de session**.

        Trente photos rapportées d'un week-end forment une session, pas trente
        décisions : une file qui demande trente gestes ne se vide jamais, et une file
        qu'on ne vide jamais cesse d'être lue au bout d'une semaine.

        La fenêtre est bornée (`TRIAGE_WINDOW`) parce que `DocumentViewSet` n'est pas
        encore paginé : sans elle, ce panneau chargerait toute la photothèque du foyer
        — l'intégralité, puisque l'introduction du champ n'a rien backfillé.
        """
        queryset = untriaged(self.get_queryset()).order_by('-effective_date', '-id')
        total = queryset.count()

        window = list(queryset[:TRIAGE_WINDOW])
        clusters = cluster_sessions(
            window,
            limit=TRIAGE_CLUSTERS,
            window_was_full=len(window) >= TRIAGE_WINDOW,
        )

        serializer_context = {'request': request}
        return Response(
            {
                'total': total,
                'clusters': [
                    {
                        # La photo la plus récente de la grappe : une clé stable d'un
                        # rechargement à l'autre, qui disparaît avec la grappe.
                        'key': str(cluster['photos'][0].id),
                        'start': cluster['oldest'],
                        'end': cluster['newest'],
                        'count': len(cluster['photos']),
                        'photos': DocumentSerializer(
                            cluster['photos'], many=True, context=serializer_context
                        ).data,
                    }
                    for cluster in clusters
                ],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], url_path='set_purpose')
    def set_purpose(self, request):
        """Pose une intention sur un lot de photos : `{document_ids, purpose, overwrite}`.

        **Le lot n'écrase jamais un choix déjà fait.** Une grappe dont certaines photos
        portent déjà une intention est le cas normal, pas l'exception : elle se range
        sans toucher au travail déjà fait, et la réponse dit combien ont été laissées.
        Écraser reste possible, mais c'est un geste explicite (`overwrite: true`) — même
        règle que l'éditeur de ventilation, qui ne détache jamais par effet de bord.

        Une intention vide est **refusée** : « détrier » trente photos d'un coup serait
        une destruction de masse déguisée en raccourci, et le geste unitaire existe pour
        ça (PATCH sur la photo).

        **Tout ou rien** sur les identifiants, comme `bulk_add_zones` : en ranger la
        moitié sans le dire laisserait l'utilisateur croire son tri fait.
        """
        raw_documents = request.data.get('document_ids', None)
        if raw_documents is None:
            raise ValidationError({'document_ids': 'document_ids is required.'})
        if isinstance(raw_documents, str) or not isinstance(raw_documents, (list, tuple)):
            raise ValidationError({'document_ids': 'document_ids must be a list.'})

        purpose = (request.data.get('purpose') or '').strip()
        if not purpose:
            raise ValidationError({'purpose': 'purpose is required and cannot be empty.'})
        if purpose not in {value for value, _label in Document.Purpose.choices}:
            raise ValidationError({'purpose': f'Unknown purpose: {purpose!r}.'})

        document_ids = []
        for value in raw_documents:
            text = str(value).strip()
            if not text:
                continue
            if not text.isdigit():
                raise ValidationError({'document_ids': f'Invalid document id: {text}'})
            document_ids.append(int(text))
        document_ids = list(dict.fromkeys(document_ids))
        if not document_ids:
            raise ValidationError({'document_ids': 'document_ids cannot be empty.'})

        # `get_queryset()` porte déjà le scope foyer **et** la confidentialité : on ne
        # refait pas ce filtrage ici, sous peine de le voir dériver.
        documents = list(self.get_queryset().filter(pk__in=document_ids))
        if len(documents) != len(document_ids):
            raise ValidationError({'document_ids': 'Invalid document or access denied.'})

        not_photos = [document for document in documents if document.type != 'photo']
        if not_photos:
            raise ValidationError({'document_ids': 'Only a photo can carry a purpose.'})

        overwrite = bool(request.data.get('overwrite', False))
        # Reposer la même intention n'est pas un conflit : c'est sans effet, et le dire
        # « ignoré » ferait passer un lot idempotent pour un lot à moitié appliqué.
        to_update = [
            document for document in documents
            if overwrite or not document.purpose or document.purpose == purpose
        ]
        skipped = len(documents) - len(to_update)

        if to_update:
            with transaction.atomic():
                Document.objects.filter(pk__in=[d.pk for d in to_update]).update(
                    purpose=purpose,
                    updated_at=timezone.now(),
                )

        return Response(
            {'updated': len(to_update), 'skipped': skipped},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def reprocess_ocr(self, request, pk=None):
        """Re-run text extraction on this document and persist the result."""
        document = self.get_object()
        _run_extraction(document, feature="ocr_upload", user=request.user)
        document.refresh_from_db()
        serializer = DocumentDetailSerializer(
            document,
            context={
                'request': request,
                'recent_interaction_candidates': get_recent_interaction_candidates(
                    request,
                    document.household,
                    document_id=document.id,
                ),
            },
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
