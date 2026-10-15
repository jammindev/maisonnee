import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from documents.models import Document
from households.models import Household, HouseholdMember
from interactions.models import Interaction
from django.contrib.contenttypes.models import ContentType

from documents.models import DocumentLink
from documents.services import link_document
from projects.models import Project
from zones.models import Zone


def _jpeg_bytes(width: int = 100, height: int = 100, color: str = "red") -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _household(name: str) -> Household:
    return Household.objects.create(name=name)


def _membership(user, household, role=HouseholdMember.Role.OWNER):
    return HouseholdMember.objects.create(user=user, household=household, role=role)


@pytest.fixture
def owner(db):
    return UserFactory(email="documents-owner@example.com")


@pytest.fixture
def household(db, owner):
    instance = _household("Documents House")
    _membership(owner, instance)
    owner.active_household = instance
    owner.save(update_fields=["active_household"])
    return instance


@pytest.fixture
def owner_client(owner):
    return _client_for(owner)


def _interaction(household, owner):
    zone = Zone.objects.create(household=household, name="Kitchen", created_by=owner)
    interaction = Interaction.objects.create(
        household=household,
        created_by=owner,
        subject="Invoice",
        type="expense",
        occurred_at="2026-03-07T10:00:00Z",
    )
    interaction.zones.add(zone)
    return interaction


@pytest.mark.django_db
class TestDocumentsApi:
    @override_settings(MEDIA_ROOT='/tmp/house-test-media')
    def test_upload_document_multipart_returns_detail_url_and_without_activity(self, owner_client, household):
        url = reverse('document-upload')
        upload = SimpleUploadedFile('invoice.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        response = owner_client.post(
            url,
            {'file': upload, 'name': 'Invoice March', 'type': 'invoice'},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['detail_url'].endswith(f"/app/documents/{response.data['document']['id']}/")
        assert response.data['document']['qualification']['qualification_state'] == 'without_activity'
        assert response.data['document']['metadata']['size'] == len(b'%PDF-1.4 test')

    def test_create_document_uses_selected_household(self, owner_client, household):
        url = reverse("document-list")
        response = owner_client.post(
            url,
            {"file_path": "docs/invoice.pdf", "name": "Invoice", "mime_type": "application/pdf", "type": "invoice"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Document.objects.filter(id=response.data["id"], household=household).exists()

    def test_create_document_with_interaction_infers_household(self, owner_client, owner, household):
        interaction = _interaction(household, owner)
        url = reverse("document-list")
        response = owner_client.post(
            url,
            {"file_path": "docs/manual.pdf", "name": "Manual", "mime_type": "application/pdf", "type": "manual", "interaction": str(interaction.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        document = Document.objects.get(id=response.data["id"])
        assert document.household == household
        assert document.interaction == interaction

    def test_reject_document_when_selected_household_mismatches_interaction(self, owner_client, owner, household):
        interaction = _interaction(household, owner)
        other_household = _household("Other Docs House")
        _membership(owner, other_household)

        owner.active_household = other_household
        owner.save(update_fields=["active_household"])

        url = reverse("document-list")
        response = owner_client.post(
            url,
            {"file_path": "docs/bad.pdf", "name": "Bad", "mime_type": "application/pdf", "type": "document", "interaction": str(interaction.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "household_id" in response.data

    def test_by_type_groups_documents(self, owner_client, owner, household):
        Document.objects.create(household=household, created_by=owner, file_path="docs/a.pdf", name="A", mime_type="application/pdf", type="document")
        Document.objects.create(household=household, created_by=owner, file_path="docs/b.jpg", name="B", mime_type="image/jpeg", type="photo")

        url = reverse("document-by-type")
        response = owner_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["document"]["count"] == 1
        assert response.data["photo"]["count"] == 1

    def test_reprocess_ocr_runs_extraction_and_returns_document(self, monkeypatch, owner_client, owner, household):
        document = Document.objects.create(
            household=household,
            created_by=owner,
            file_path="docs/reprocess.pdf",
            name="OCR",
            mime_type="application/pdf",
            type="document",
        )

        monkeypatch.setattr(
            "documents.views.extract_text",
            lambda doc, **kw: ("Extracted via reprocess", "pypdf"),
        )

        url = reverse("document-reprocess-ocr", kwargs={"pk": document.id})
        response = owner_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ocr_text"] == "Extracted via reprocess"
        document.refresh_from_db()
        assert document.ocr_text == "Extracted via reprocess"
        assert document.metadata["ocr_method"] == "pypdf"
        assert "ocr_extracted_at" in document.metadata

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-heic')
    def test_upload_heic_image_is_normalized_to_jpeg(self, monkeypatch, owner_client, household):
        """HEIC magic bytes are accepted; the file is transcoded to JPEG before save."""
        monkeypatch.setattr(
            "documents.views.normalize_image",
            lambda f, mime: (
                SimpleUploadedFile("photo.jpg", _jpeg_bytes(), content_type="image/jpeg"),
                "image/jpeg",
                {"transcoded": True, "resized": False, "original_mime_type": "image/heic", "final_dimensions": [100, 100]},
            ),
        )
        monkeypatch.setattr("documents.views.extract_text", lambda doc, **kw: ("Text from HEIC", "vision_haiku"))

        heic_payload = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 60
        upload = SimpleUploadedFile("photo.heic", heic_payload, content_type="image/heic")

        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "HEIC photo", "type": "document"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        document = Document.objects.get(pk=response.data["document"]["id"])
        assert document.mime_type == "image/jpeg"
        assert document.file_path.endswith(".jpg")
        assert document.ocr_text == "Text from HEIC"
        assert document.metadata["ocr_method"] == "vision_haiku"
        assert document.metadata["original_mime_type"] == "image/heic"
        assert document.metadata["normalized"] is True

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-ocr')
    def test_upload_image_runs_text_extraction(self, monkeypatch, owner_client, household):
        monkeypatch.setattr("documents.views.extract_text", lambda doc, **kw: ("Receipt total 12.50", "vision_haiku"))

        upload = SimpleUploadedFile("receipt.jpg", _jpeg_bytes(), content_type="image/jpeg")
        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "Receipt", "type": "receipt"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        document = Document.objects.get(pk=response.data["document"]["id"])
        assert document.ocr_text == "Receipt total 12.50"
        assert document.metadata["ocr_method"] == "vision_haiku"
        assert "ocr_extracted_at" in document.metadata

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-failsoft')
    def test_upload_succeeds_when_extraction_throws(self, monkeypatch, owner_client, household):
        def boom(_doc):
            raise RuntimeError("vision exploded")

        monkeypatch.setattr("documents.views.extract_text", boom)

        upload = SimpleUploadedFile("receipt.jpg", _jpeg_bytes(), content_type="image/jpeg")
        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "Receipt", "type": "receipt"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        document = Document.objects.get(pk=response.data["document"]["id"])
        assert document.ocr_text == ""
        assert document.metadata["ocr_method"] == "skipped"

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-nul')
    def test_upload_succeeds_when_extracted_text_carries_nul_bytes(
        self, monkeypatch, owner_client, household
    ):
        """Un PDF de formulaire signé rend du texte contenant des NUL (0x00).

        Postgres refuse 0x00 dans une colonne texte : le `save` qui persiste le
        résultat de l'extraction levait `ValueError`, *après* le commit du
        document. L'envoi répondait 500 sur une opération réussie, et
        l'utilisateur réessayait — donc créait un doublon.
        """
        # On mocke la couche *sous* `extract_text`, pour que l'enveloppe qui
        # nettoie soit bien celle que la vue traverse : c'est la chaîne réelle
        # qui doit tenir, pas le seul helper pris à part.
        monkeypatch.setattr(
            "documents.extraction._extract_text",
            lambda doc, **kw: ("ATTESTATION\x00 SUR L'HONNEUR\x00", "pypdf"),
        )

        upload = SimpleUploadedFile("attestation.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "Attestation", "type": "document"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        document = Document.objects.get(pk=response.data["document"]["id"])
        assert "\x00" not in document.ocr_text
        assert document.ocr_text == "ATTESTATION SUR L'HONNEUR"
        assert document.metadata["ocr_method"] == "pypdf"

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-persist-boom')
    def test_upload_succeeds_when_persisting_the_extraction_throws(
        self, monkeypatch, owner_client, household
    ):
        """Le document est déjà commité : rien de ce qui suit ne doit répondre 500.

        L'extraction est un bonus. Faire échouer la requête sur son écriture
        annonce un échec sur une opération réussie — et pousse à réessayer.
        """
        monkeypatch.setattr(
            "documents.views.extract_text",
            lambda doc, **kw: ("texte", "pypdf"),
        )

        original_save = Document.save

        def boom(self, *args, **kwargs):
            if kwargs.get("update_fields"):
                raise RuntimeError("postgres said no")
            return original_save(self, *args, **kwargs)

        monkeypatch.setattr(Document, "save", boom)

        upload = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "Doc", "type": "document"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Document.objects.filter(pk=response.data["document"]["id"]).exists()

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-photo-skip')
    def test_upload_photo_type_skips_extraction(self, monkeypatch, owner_client, household):
        """type='photo' goes to the photo grid; running Vision OCR on it is wasted."""
        from rest_framework import serializers as drf_serializers

        class _PermissiveUploadSerializer(drf_serializers.Serializer):
            file = drf_serializers.FileField()
            name = drf_serializers.CharField(required=False, allow_blank=True, max_length=255)
            type = drf_serializers.ChoiceField(
                choices=[(v, l) for v, l in Document.DOCUMENT_TYPES],
                required=False,
                allow_null=True,
            )
            notes = drf_serializers.CharField(required=False, allow_blank=True)
            is_private = drf_serializers.BooleanField(required=False, default=False)

        monkeypatch.setattr("documents.views.DocumentUploadSerializer", _PermissiveUploadSerializer)
        monkeypatch.setattr("documents.views.generate_thumbnails", lambda doc: None)

        extract_calls = []

        def fake_extract(doc):
            extract_calls.append(doc.pk)
            return ("should not run", "vision_haiku")

        monkeypatch.setattr("documents.views.extract_text", fake_extract)

        upload = SimpleUploadedFile("vacation.jpg", _jpeg_bytes(), content_type="image/jpeg")
        response = owner_client.post(
            reverse("document-upload"),
            {"file": upload, "name": "Vacation", "type": "photo"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        document = Document.objects.get(pk=response.data["document"]["id"])
        assert document.type == "photo"
        assert document.ocr_text == ""
        assert "ocr_method" not in (document.metadata or {})
        assert "ocr_extracted_at" not in (document.metadata or {})
        assert extract_calls == [], f"extract_text should not run for photos (got {extract_calls})"

    def test_upload_requires_household_context(self, owner_client):
        url = reverse('document-upload')
        upload = SimpleUploadedFile('invoice.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        response = owner_client.post(url, {'file': upload}, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'household_id' in response.data

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-photo-upload')
    def test_upload_accepts_type_photo(self, owner_client, household):
        url = reverse('document-upload')
        upload = SimpleUploadedFile('vacation.jpg', _jpeg_bytes(), content_type='image/jpeg')

        response = owner_client.post(
            url,
            {'file': upload, 'name': 'Vacation', 'type': 'photo'},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        assert document.type == 'photo'
        assert document.household == household

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-zone-upload')
    def test_upload_with_zone_creates_zone_document(self, owner_client, owner, household):
        zone = Zone.objects.create(household=household, name='Living room', created_by=owner)
        url = reverse('document-upload')
        upload = SimpleUploadedFile('living.jpg', _jpeg_bytes(), content_type='image/jpeg')

        response = owner_client.post(
            url,
            {'file': upload, 'type': 'photo', 'zone': str(zone.id)},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        link = DocumentLink.objects.get(document=document)
        assert str(link.object_id) == str(zone.id)
        assert link.role == 'photo'
        assert link.created_by == owner

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-zone-doc')
    def test_upload_with_zone_uses_role_document_for_non_photo(self, owner_client, owner, household):
        zone = Zone.objects.create(household=household, name='Office', created_by=owner)
        url = reverse('document-upload')
        upload = SimpleUploadedFile('manual.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        response = owner_client.post(
            url,
            {'file': upload, 'type': 'manual', 'zone': str(zone.id)},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        document = Document.objects.get(pk=response.data['document']['id'])
        link = DocumentLink.objects.get(document=document)
        assert link.role == 'document'

    @override_settings(MEDIA_ROOT='/tmp/house-test-media-zone-foreign')
    def test_upload_rejects_zone_from_another_household(self, owner_client, owner, household):
        other = _household('Other house')
        foreign_zone = Zone.objects.create(household=other, name='Foreign zone', created_by=owner)
        url = reverse('document-upload')
        upload = SimpleUploadedFile('manual.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        response = owner_client.post(
            url,
            {'file': upload, 'type': 'manual', 'zone': str(foreign_zone.id)},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'zone' in response.data
        assert not Document.objects.filter(name='manual.pdf').exists()
        assert not DocumentLink.objects.exists()

    def test_list_exposes_qualification_flags_from_interaction_documents(self, owner_client, owner, household):
        linked_document = Document.objects.create(
            household=household,
            created_by=owner,
            file_path='docs/linked.pdf',
            name='Linked',
            mime_type='application/pdf',
            type='document',
        )
        unlinked_document = Document.objects.create(
            household=household,
            created_by=owner,
            file_path='docs/unlinked.pdf',
            name='Unlinked',
            mime_type='application/pdf',
            type='document',
        )
        interaction = _interaction(household, owner)
        link_document(entity=interaction, document=linked_document, role='attachment')

        url = reverse('document-list')
        response = owner_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        payload_by_name = {item['name']: item for item in response.data}
        assert payload_by_name['Linked']['qualification']['qualification_state'] == 'activity_linked'
        assert payload_by_name['Linked']['qualification']['linked_interactions_count'] == 1
        assert payload_by_name['Unlinked']['qualification']['qualification_state'] == 'without_activity'
        assert payload_by_name['Unlinked']['linked_interactions'] == []

    def test_detail_exposes_linked_interactions_secondary_contexts_and_recent_candidates(self, owner_client, owner, household):  # noqa: E501
        zone = Zone.objects.create(household=household, name='Boiler room', created_by=owner)
        document = Document.objects.create(
            household=household,
            created_by=owner,
            file_path='docs/manual.pdf',
            name='Boiler manual',
            mime_type='application/pdf',
            type='manual',
            notes='Keep near the boiler.',
            ocr_text='Boiler maintenance instructions',
        )
        linked_interaction = Interaction.objects.create(
            household=household,
            created_by=owner,
            subject='Annual boiler maintenance',
            type='maintenance',
            occurred_at='2026-03-07T10:00:00Z',
        )
        linked_interaction.zones.add(zone)
        recent_interaction = Interaction.objects.create(
            household=household,
            created_by=owner,
            subject='Heating inspection',
            type='inspection',
            occurred_at='2026-03-08T10:00:00Z',
        )
        recent_interaction.zones.add(zone)
        link_document(entity=linked_interaction, document=document, role='attachment')
        link_document(entity=zone, document=document, user=owner)
        project = Project.objects.create(
            household=household,
            created_by=owner,
            title='Heating project',
            type=Project.Type.MAINTENANCE,
            status=Project.Status.ACTIVE,
        )
        link_document(entity=project, document=document, user=owner)

        url = reverse('document-detail', kwargs={'pk': document.id})
        response = owner_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['qualification']['qualification_state'] == 'activity_linked'
        assert response.data['qualification']['has_secondary_context'] is True
        assert response.data['linked_interactions'][0]['subject'] == 'Annual boiler maintenance'
        assert response.data['zone_links'][0]['zone_name'] == 'Boiler room'
        assert response.data['project_links'][0]['project_name'] == 'Heating project'
        assert {item['subject'] for item in response.data['recent_interaction_candidates']} == {
            'Heating inspection',
        }

    def test_list_filters_by_project(self, owner_client, owner, household):
        linked = Document.objects.create(
            household=household, created_by=owner,
            file_path='docs/p-linked.pdf', name='Linked',
            mime_type='application/pdf', type='document',
        )
        Document.objects.create(
            household=household, created_by=owner,
            file_path='docs/p-other.pdf', name='Other',
            mime_type='application/pdf', type='document',
        )
        project = Project.objects.create(
            household=household, created_by=owner, title='Renovation',
        )
        link_document(entity=project, document=linked, user=owner)

        url = reverse('document-list')
        response = owner_client.get(url, {'project': str(project.id)})

        assert response.status_code == status.HTTP_200_OK
        names = {item['name'] for item in response.data}
        assert names == {'Linked'}

    def test_list_filters_by_zone(self, owner_client, owner, household):
        zone = Zone.objects.create(household=household, name='Garage', created_by=owner)
        linked = Document.objects.create(
            household=household, created_by=owner,
            file_path='docs/z-linked.pdf', name='ZoneLinked',
            mime_type='application/pdf', type='document',
        )
        Document.objects.create(
            household=household, created_by=owner,
            file_path='docs/z-other.pdf', name='ZoneOther',
            mime_type='application/pdf', type='document',
        )
        link_document(entity=zone, document=linked, user=owner)

        url = reverse('document-list')
        response = owner_client.get(url, {'zone': str(zone.id)})

        assert response.status_code == status.HTTP_200_OK
        names = {item['name'] for item in response.data}
        assert names == {'ZoneLinked'}


# ---------------------------------------------------------------------------
# TestDocumentPrivacy
# Covers the is_private field: upload serializer, list queryset filtering,
# PATCH permission guard, and serve_protected_media access control.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDocumentPrivacy:
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_document(self, household, created_by, *, is_private=False, file_path=None, **kwargs):
        """Create and return a Document belonging to *household*."""
        kwargs.setdefault("name", "Test Document")
        kwargs.setdefault("mime_type", "application/pdf")
        kwargs.setdefault("type", "document")
        return Document.objects.create(
            household=household,
            created_by=created_by,
            file_path=file_path or f"documents/{household.id}/2026/03/test-{created_by.id}.pdf",
            is_private=is_private,
            **kwargs,
        )

    def _upload_payload(self, **overrides):
        """Return a valid multipart-style payload dict for document-upload."""
        defaults = {
            "name": "Private Invoice",
            "type": "invoice",
        }
        defaults.update(overrides)
        return defaults

    def _add_member(self, user, household, role=HouseholdMember.Role.MEMBER):
        """Add *user* to *household* with *role* and set active_household."""
        HouseholdMember.objects.create(user=user, household=household, role=role)
        user.active_household = household
        user.save(update_fields=["active_household"])

    # ------------------------------------------------------------------
    # 1. Upload with is_private=True persists the flag
    # ------------------------------------------------------------------

    @override_settings(MEDIA_ROOT='/tmp/house-test-media')
    def test_upload_with_is_private_true_creates_private_document(self, owner_client, owner, household):
        url = reverse("document-upload")
        upload = SimpleUploadedFile("secret.pdf", b"%PDF-1.4 secret", content_type="application/pdf")
        payload = self._upload_payload(is_private="true")  # multipart sends strings

        response = owner_client.post(
            url,
            {"file": upload, **payload},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        doc = Document.objects.get(id=response.data["document"]["id"])
        assert doc.is_private is True

    # ------------------------------------------------------------------
    # 2. Upload without is_private defaults to public
    # ------------------------------------------------------------------

    @override_settings(MEDIA_ROOT='/tmp/house-test-media')
    def test_upload_without_is_private_defaults_to_public(self, owner_client, owner, household):
        url = reverse("document-upload")
        upload = SimpleUploadedFile("public.pdf", b"%PDF-1.4 public", content_type="application/pdf")

        response = owner_client.post(
            url,
            {"file": upload, "name": "Public Doc", "type": "document"},
            format="multipart",
        )

        assert response.status_code == status.HTTP_201_CREATED
        doc = Document.objects.get(id=response.data["document"]["id"])
        assert doc.is_private is False

    # ------------------------------------------------------------------
    # 3. Owner sees their own private documents in the list
    # ------------------------------------------------------------------

    def test_owner_sees_own_private_document_in_list(self, owner_client, owner, household):
        private_doc = self._create_document(household, owner, is_private=True, name="Owner Private")

        url = reverse("document-list")
        response = owner_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        returned_ids = [item["id"] for item in response.data]
        assert private_doc.id in returned_ids

    # ------------------------------------------------------------------
    # 4. Another member does NOT see private documents of other members
    # ------------------------------------------------------------------

    def test_member_cannot_see_other_members_private_document_in_list(self, owner, household):
        private_doc = self._create_document(household, owner, is_private=True, name="Owner Private")

        other_member = UserFactory()
        self._add_member(other_member, household)
        other_client = APIClient()
        other_client.force_authenticate(user=other_member)

        url = reverse("document-list")
        response = other_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        returned_ids = [item["id"] for item in response.data]
        assert private_doc.id not in returned_ids

    # ------------------------------------------------------------------
    # 5. PATCH is_private: document owner can toggle the flag
    # ------------------------------------------------------------------

    def test_owner_can_patch_is_private(self, owner_client, owner, household):
        doc = self._create_document(household, owner, is_private=False)

        url = reverse("document-detail", args=[doc.id])
        response = owner_client.patch(url, {"is_private": True}, format="json")

        assert response.status_code == status.HTTP_200_OK
        doc.refresh_from_db()
        assert doc.is_private is True

    # ------------------------------------------------------------------
    # 6. PATCH is_private: non-owner household member gets 403
    # ------------------------------------------------------------------

    def test_non_owner_cannot_patch_is_private(self, owner, household):
        doc = self._create_document(household, owner, is_private=False)

        other_member = UserFactory()
        self._add_member(other_member, household)
        other_client = APIClient()
        other_client.force_authenticate(user=other_member)

        url = reverse("document-detail", args=[doc.id])
        response = other_client.patch(url, {"is_private": True}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        # DB must not have been mutated
        doc.refresh_from_db()
        assert doc.is_private is False

    # ------------------------------------------------------------------
    # 7. serve_protected_media: owner gets 200 + X-Accel-Redirect on their
    #    private document
    # ------------------------------------------------------------------

    @override_settings(PROTECTED_MEDIA_ACCEL=True)
    def test_serve_protected_media_owner_can_access_private_document(self, owner, household):
        file_path = f"documents/{household.id}/2026/03/private-owner.pdf"
        self._create_document(household, owner, is_private=True, file_path=file_path)

        django_client = Client()
        django_client.force_login(owner)

        response = django_client.get(f"/media/{file_path}")

        assert response.status_code == 200
        assert response.get("X-Accel-Redirect") == f"/_protected_media/{file_path}"

    # ------------------------------------------------------------------
    # 8. serve_protected_media: non-owner member gets 403 on private document
    # ------------------------------------------------------------------

    @override_settings(PROTECTED_MEDIA_ACCEL=True)
    def test_serve_protected_media_non_owner_gets_403_on_private_document(self, owner, household):
        file_path = f"documents/{household.id}/2026/03/private-other.pdf"
        self._create_document(household, owner, is_private=True, file_path=file_path)

        other_member = UserFactory()
        self._add_member(other_member, household)

        django_client = Client()
        django_client.force_login(other_member)

        response = django_client.get(f"/media/{file_path}")

        assert response.status_code == 403