"""Tests for document text extraction (Vision + pypdf), with the SDK mocked."""
from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.core.files.storage import default_storage
from PIL import Image
from pypdf import PdfWriter

from documents import extraction
from documents.models import Document


class _FakeLLMClient:
    """Stands in for agent.llm's client: only vision_extract matters here."""

    def __init__(self, text="", raises: Exception | None = None):
        self.text = text
        self.raises = raises
        self.calls: list[dict] = []

    def vision_extract(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            text=self.text, input_tokens=10, output_tokens=5, duration_ms=1, model="fake"
        )


def _save(path: str, content: bytes) -> str:
    if default_storage.exists(path):
        default_storage.delete(path)
    return default_storage.save(path, io.BytesIO(content))


def _make_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (10, 10), "red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _isolated_media(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    yield


@pytest.mark.django_db
class TestExtractText:
    def _make_document(self, household, owner, *, file_path: str, mime: str) -> Document:
        return Document.objects.create(
            household=household,
            created_by=owner,
            file_path=file_path,
            name="doc",
            mime_type=mime,
            type="document",
        )

    def test_returns_skipped_when_file_missing(self, household, owner):
        document = self._make_document(household, owner, file_path="missing.pdf", mime="application/pdf")

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "skipped"

    def test_image_uses_vision_haiku(self, monkeypatch, household, owner):
        path = _save("docs/test.jpg", _make_jpeg_bytes())
        document = self._make_document(household, owner, file_path=path, mime="image/jpeg")

        fake_client = _FakeLLMClient(text="Hello from receipt")
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: fake_client)

        text, method = extraction.extract_text(document)

        assert text == "Hello from receipt"
        assert method == "vision_haiku"
        assert len(fake_client.calls) == 1
        # The call is traced with feature + household for AIUsageLog.
        assert fake_client.calls[0]["feature"] == "ocr_upload"
        assert fake_client.calls[0]["household_id"] == household.id

    def test_image_returns_vision_empty_when_client_unavailable(self, monkeypatch, household, owner):
        path = _save("docs/test.jpg", _make_jpeg_bytes())
        document = self._make_document(household, owner, file_path=path, mime="image/jpeg")

        monkeypatch.setattr(extraction, "_get_llm_client", lambda: None)

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "vision_empty"

    def test_image_failure_in_sdk_returns_vision_empty(self, monkeypatch, household, owner):
        path = _save("docs/test.jpg", _make_jpeg_bytes())
        document = self._make_document(household, owner, file_path=path, mime="image/jpeg")

        fake_client = _FakeLLMClient(raises=RuntimeError("boom"))
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: fake_client)

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "vision_empty"

    def test_image_with_no_text_returns_vision_empty(self, monkeypatch, household, owner):
        path = _save("docs/test.jpg", _make_jpeg_bytes())
        document = self._make_document(household, owner, file_path=path, mime="image/jpeg")

        fake_client = _FakeLLMClient(text="")
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: fake_client)

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "vision_empty"
        # Vision was actually called — that's the whole point of this state.
        assert len(fake_client.calls) == 1

    def test_pdf_with_empty_pypdf_returns_pdf_vision_empty_when_no_client(self, monkeypatch, household, owner):
        """Blank PDF: pypdf returns empty, Vision fallback can't run (no client) → pdf_vision_empty."""
        path = _save("docs/blank.pdf", _make_pdf_bytes())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: None)

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "pdf_vision_empty"

    def test_scanned_pdf_falls_back_to_vision_per_page(self, monkeypatch, household, owner):
        """pypdf returns empty (image-only PDF). Vision OCR-s each page."""
        path = _save("docs/scanned.pdf", _make_pdf_bytes())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")

        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "")
        monkeypatch.setattr(
            extraction, "_extract_pdf_with_vision",
            lambda _b, **_kw: "Page 1 text\n\nPage 2 text",
        )

        text, method = extraction.extract_text(document)

        assert text == "Page 1 text\n\nPage 2 text"
        assert method == "pdf_vision_haiku"

    def test_scanned_pdf_renders_pages_via_pypdfium(self, monkeypatch, household, owner):
        """End-to-end: real pypdfium rendering + mocked Vision client returning text per call."""
        path = _save("docs/scanned-real.pdf", _make_pdf_bytes())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")

        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "")

        call_count = {"n": 0}

        def fake_vision(_bytes, _media, **_kw):
            call_count["n"] += 1
            return f"Page {call_count['n']}"

        monkeypatch.setattr(extraction, "_extract_with_vision", fake_vision)
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: object())

        text, method = extraction.extract_text(document)

        assert method == "pdf_vision_haiku"
        assert "Page 1" in text

    def test_scanned_pdf_keeps_partial_text_when_some_pages_fail(self, monkeypatch, household, owner):
        """If Vision raises on one page, other pages' text is still kept."""
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_blank_page(width=72, height=72)
        buffer = io.BytesIO()
        writer.write(buffer)
        path = _save("docs/partial.pdf", buffer.getvalue())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")

        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "")
        monkeypatch.setattr(extraction, "_get_llm_client", lambda: object())

        call = {"n": 0}

        def flaky_vision(_b, _m, **_kw):
            call["n"] += 1
            if call["n"] == 1:
                raise RuntimeError("page 1 boom")
            return "page 2 ok"

        monkeypatch.setattr(extraction, "_extract_with_vision", flaky_vision)

        text, method = extraction.extract_text(document)

        assert "page 2 ok" in text
        assert method == "pdf_vision_haiku"

    def test_pypdf_text_pdfs_skip_vision_fallback(self, monkeypatch, household, owner):
        """Text-based PDFs: pypdf works, Vision is never called."""
        path = _save("docs/text.pdf", _make_pdf_bytes())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")

        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "I am text from pypdf")

        def must_not_run(_b, _m, **_kw):
            raise AssertionError("Vision should not run when pypdf returns text")

        monkeypatch.setattr(extraction, "_extract_with_vision", must_not_run)

        text, method = extraction.extract_text(document)

        assert text == "I am text from pypdf"
        assert method == "pypdf"

    def test_pdf_extraction_uses_pypdf(self, monkeypatch, household, owner):
        path = _save("docs/text.pdf", _make_pdf_bytes())
        document = self._make_document(household, owner, file_path=path, mime="application/pdf")

        fake_page = MagicMock()
        fake_page.extract_text.return_value = "Some PDF body"
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        class _Reader:
            def __init__(self, _):
                self.pages = fake_reader.pages

        monkeypatch.setattr("pypdf.PdfReader", _Reader)

        text, method = extraction.extract_text(document)

        assert text == "Some PDF body"
        assert method == "pypdf"

    def test_unsupported_mime_returns_skipped(self, household, owner):
        path = _save("docs/file.txt", b"plain text")
        document = self._make_document(household, owner, file_path=path, mime="text/plain")

        text, method = extraction.extract_text(document)

        assert text == ""
        assert method == "skipped"


@pytest.fixture
def owner(db):
    from accounts.tests.factories import UserFactory

    return UserFactory(email="extraction-owner@example.com")


@pytest.fixture
def household(db, owner):
    from households.models import Household, HouseholdMember

    instance = Household.objects.create(name="Extraction House")
    HouseholdMember.objects.create(user=owner, household=instance, role=HouseholdMember.Role.OWNER)
    owner.active_household = instance
    owner.save(update_fields=["active_household"])
    return instance


@pytest.mark.django_db
class TestExtractedTextNeverCarriesNulBytes:
    """Postgres refuse 0x00 dans une colonne texte.

    Le texte extrait est du contenu **non maîtrisé** : il se nettoie à la
    frontière qui le produit, une fois, plutôt qu'à chacun de ses trois
    consommateurs (envoi, backfill, reprocess). Le chemin PDF, où le NUL
    déclenche en plus un repli, a sa propre classe plus bas.
    """

    def test_strip_nul_removes_only_the_nul(self):
        assert extraction._strip_nul("a\x00b") == "ab"
        assert extraction._strip_nul("déjà\x00 vu") == "déjà vu"
        assert extraction._strip_nul("propre") == "propre"
        assert extraction._strip_nul("") == ""

    def test_vision_text_reaches_the_caller_without_nul(self, monkeypatch, household, owner):
        path = _save("docs/scan.jpg", _make_jpeg_bytes())
        document = Document.objects.create(
            household=household,
            created_by=owner,
            file_path=path,
            name="scan",
            mime_type="image/jpeg",
            type="document",
        )
        monkeypatch.setattr(
            extraction, "_extract_with_vision", lambda *a, **kw: "FACTURE\x00 2026"
        )

        text, method = extraction.extract_text(document)

        assert method == "vision_haiku"
        assert "\x00" not in text
        assert text == "FACTURE 2026"


@pytest.mark.django_db
class TestALossyTextLayerFallsBackToVision:
    """Un NUL dit que le PDF ne sait pas nommer un de ses glyphes.

    Cas réel : les ligatures `fi`/`fl` d'une fonte Type3 sous-ensemblée, dont
    la table ToUnicode déclare `<AB> -> <0000>` et dont les glyphes s'appellent
    `/gAB`. « bénéficiaire » ressort « béné<NUL>ciaire » : le caractère n'est
    récupérable nulle part dans la couche texte, seuls les pixels le portent.
    C'est exactement la situation d'un PDF scanné, donc le même repli.
    """

    def _pdf_document(self, household, owner, path):
        return Document.objects.create(
            household=household,
            created_by=owner,
            file_path=path,
            name="form",
            mime_type="application/pdf",
            type="document",
        )

    def test_nul_in_pypdf_text_triggers_the_vision_fallback(self, monkeypatch, household, owner):
        path = _save("docs/ligatures.pdf", _make_pdf_bytes())
        document = self._pdf_document(household, owner, path)
        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "le béné\x00ciaire")
        monkeypatch.setattr(
            extraction, "_extract_pdf_with_vision", lambda *a, **kw: "le bénéficiaire"
        )

        text, method = extraction.extract_text(document)

        assert method == "pdf_vision_haiku"
        assert text == "le bénéficiaire"

    def test_degraded_text_is_kept_and_flagged_when_vision_is_unavailable(
        self, monkeypatch, household, owner
    ):
        """Pas de clé Anthropic : on garde le texte, on ne perd pas le document.

        Mais il se dit `pypdf_lossy` — un texte faux qu'on croit bon ne se
        corrige jamais.
        """
        path = _save("docs/ligatures-nokey.pdf", _make_pdf_bytes())
        document = self._pdf_document(household, owner, path)
        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "le béné\x00ciaire")
        # Ce que rend `_extract_pdf_with_vision` sans client configuré.
        monkeypatch.setattr(extraction, "_extract_pdf_with_vision", lambda *a, **kw: "")

        text, method = extraction.extract_text(document)

        assert method == "pypdf_lossy"
        assert text == "le bénéciaire"
        assert "\x00" not in text

    def test_a_clean_pdf_never_pays_for_vision(self, monkeypatch, household, owner):
        """Le repli coûte un appel par page : il ne se déclenche pas pour rien."""
        path = _save("docs/clean.pdf", _make_pdf_bytes())
        document = self._pdf_document(household, owner, path)
        monkeypatch.setattr(extraction, "_extract_with_pypdf", lambda _b: "texte propre")

        called = []
        monkeypatch.setattr(
            extraction,
            "_extract_pdf_with_vision",
            lambda *a, **kw: called.append(1) or "",
        )

        text, method = extraction.extract_text(document)

        assert (text, method) == ("texte propre", "pypdf")
        assert called == []
