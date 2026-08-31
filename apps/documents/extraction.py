"""
Text extraction for uploaded documents.

Three pipelines:
- images → Claude Haiku 4.5 Vision (OCR)
- text-based PDFs → pypdf (fast, free)
- scanned PDFs → fallback Vision page-by-page (each page rendered as image)

Everything is fail-soft. Returning ``("", <method>)`` is a perfectly acceptable
outcome — the upload must never fail because text extraction did.
"""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Tuple

from django.conf import settings
from django.core.files.storage import default_storage

if TYPE_CHECKING:
    from documents.models import Document

logger = logging.getLogger(__name__)

VISION_MODEL = "claude-haiku-4-5"
VISION_MAX_TOKENS = 4096
DEFAULT_FEATURE = "ocr_upload"
VISION_PROMPT = (
    "Extract all visible text from this image, preserving the original line "
    "breaks and reading order. Return only the raw text — no commentary, no "
    "labels, no markdown."
)
VISION_MEDIA_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}

# DPI used when rasterizing scanned PDF pages for Vision OCR.
# Higher = better OCR quality but bigger payloads. 200 DPI is a typical
# balance — sharp enough for receipts/contracts, image stays under 2 MB.
PDF_VISION_RENDER_DPI = 200

ExtractionResult = Tuple[str, str]


def _get_llm_client():
    """Return the configured LLM client, or ``None`` when no key is set.

    Indirected so tests can patch ``apps.documents.extraction._get_llm_client``
    without touching the SDK or the network. Goes through
    ``agent.llm.get_llm_client`` so every Vision OCR call is logged into
    ``AIUsageLog`` (lot 6, #109) — extraction never talks to the SDK directly.
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    if not api_key:
        return None
    from agent.llm import get_llm_client

    return get_llm_client()


def _extract_with_vision(
    file_bytes: bytes,
    media_type: str,
    *,
    document: "Document",
    feature: str,
    user=None,
) -> str:
    client = _get_llm_client()
    if client is None:
        return ""

    response = client.vision_extract(
        image_bytes=file_bytes,
        media_type=media_type,
        prompt=VISION_PROMPT,
        feature=feature,
        household_id=document.household_id,
        user_id=getattr(user, "id", None),
        max_tokens=VISION_MAX_TOKENS,
        metadata={"document_id": str(document.pk), "mime_type": media_type},
    )
    return response.text


def _extract_with_pypdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("extraction: pypdf not installed")
        return ""

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            logger.info("extraction: pypdf page failed: %s", exc)
    return "\n\n".join(p.strip() for p in pages if p and p.strip()).strip()


def _extract_pdf_with_vision(
    file_bytes: bytes, *, document: "Document", feature: str, user=None
) -> str:
    """Render every PDF page and run Vision OCR on each. Concatenate the results.

    Used as a fallback when ``_extract_with_pypdf`` returns nothing — typically
    a scanned PDF where the pages are images embedded in a PDF wrapper. Each
    page is rasterized via pypdfium2, encoded as JPEG, then sent to Vision.
    """
    try:
        import pypdfium2  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("extraction: pypdfium2 not installed, can't OCR scanned PDFs")
        return ""

    if _get_llm_client() is None:
        return ""

    pdf = pypdfium2.PdfDocument(file_bytes)
    page_texts: list[str] = []
    scale = PDF_VISION_RENDER_DPI / 72.0
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                buffer = io.BytesIO()
                pil_image.save(buffer, format="JPEG", quality=85)
                text = _extract_with_vision(
                    buffer.getvalue(), "image/jpeg",
                    document=document, feature=feature, user=user,
                )
            except Exception as exc:
                logger.warning("extraction: pdf-vision page %d failed: %s", page_index, exc)
                continue
            if text:
                page_texts.append(text)
    finally:
        # Explicit close avoids "Cannot close object, library is destroyed"
        # warnings during interpreter shutdown / GC.
        pdf.close()
    return "\n\n".join(page_texts).strip()


def _strip_nul(text: str) -> str:
    """Retire les octets NUL (0x00) d'un texte extrait.

    Postgres refuse 0x00 dans une colonne texte — l'écriture lève `DataError`.
    Or le texte extrait n'est pas du contenu maîtrisé : un PDF de formulaire
    signé (AcroForm) en rend couramment via pypdf, et une réponse Vision peut
    en porter aussi. Un envoi a ainsi répondu 500 **après** la création du
    document : l'utilisateur voyait un échec sur une opération réussie, et
    réessayait — donc créait un doublon.

    Le nettoyage vit ici, au seul endroit qui produit ce texte, et non chez ses
    trois consommateurs (envoi, backfill, reprocess) : trois copies d'un même
    garde-fou finissent par diverger, et c'est celle qu'on oublie qui casse.
    """
    return text.replace("\x00", "") if text else text


def extract_text(
    document: "Document", *, feature: str = DEFAULT_FEATURE, user=None
) -> ExtractionResult:
    """Extract text content from a stored document — jamais d'octet NUL.

    Enveloppe :func:`_extract_text` pour garantir la propriété sur **toutes**
    ses branches, présentes et à venir. Voir :func:`_strip_nul` pour le pourquoi.
    """
    text, method = _extract_text(document, feature=feature, user=user)
    return _strip_nul(text), method


def _extract_text(
    document: "Document", *, feature: str = DEFAULT_FEATURE, user=None
) -> ExtractionResult:
    """Extract text content from a stored document.

    ``feature`` tags the AIUsageLog lines this extraction produces
    ('ocr_upload' by default, 'ocr_backfill' from the management command);
    ``user`` is the acting user when there is one (uploads).

    Returns ``(text, method)`` where ``method`` is one of:
    - ``"vision_haiku"``     : Vision called on an image, returned text
    - ``"vision_empty"``     : Vision called on an image, returned no text
    - ``"pypdf"``            : pypdf returned text from a text-based PDF
    - ``"pypdf_lossy"``      : pypdf text carrying unmapped glyphs (NUL), kept
                               because Vision was unavailable or silent
    - ``"pdf_vision_haiku"`` : pypdf was empty, Vision OCR'd each page successfully
    - ``"pdf_vision_empty"`` : pypdf was empty, Vision called on each page but no text
    - ``"skipped"``          : not attempted (no file, unsupported mime, IO error)

    The ``_empty`` variants indicate the API/library was actually invoked, which
    matters for cost accounting (a Vision call has a real $ cost even when the
    response is empty).
    """
    if not document.file_path:
        return "", "skipped"
    try:
        if not default_storage.exists(document.file_path):
            return "", "skipped"
    except OSError as exc:
        logger.info("extraction: storage check failed for %s: %s", document.file_path, exc)
        return "", "skipped"

    mime = (document.mime_type or "").lower()
    try:
        with default_storage.open(document.file_path, "rb") as fh:
            file_bytes = fh.read()
    except OSError as exc:
        logger.info("extraction: cannot read %s: %s", document.file_path, exc)
        return "", "skipped"

    if mime in VISION_MEDIA_TYPES:
        try:
            text = _extract_with_vision(
                file_bytes, VISION_MEDIA_TYPES[mime],
                document=document, feature=feature, user=user,
            )
        except Exception as exc:
            logger.warning("extraction: vision failed for %s: %s", document.file_path, exc)
            return "", "vision_empty"
        if not text:
            return "", "vision_empty"
        return text, "vision_haiku"

    if mime == "application/pdf":
        try:
            text = _extract_with_pypdf(file_bytes)
        except Exception as exc:
            logger.warning("extraction: pypdf failed for %s: %s", document.file_path, exc)
            text = ""
        if text and "\x00" not in text:
            return text, "pypdf"

        # Deux situations mènent ici, et elles se traitent pareil :
        #  - aucun texte : PDF scanné, la page est une image ;
        #  - du texte **lacunaire** : un NUL veut dire que le PDF déclare
        #    lui-même `<code> -> U+0000` pour un glyphe. C'est le cas des
        #    ligatures `fi`/`fl` des fontes Type3 sous-ensemblées, très
        #    courantes dans les formulaires administratifs — « bénéficiaire »
        #    ressort « béné<NUL>ciaire ». Le caractère est irrécupérable côté
        #    texte (la table ToUnicode et les noms de glyphes, `/gAB`, ne
        #    disent rien) : seuls les pixels le portent encore.
        try:
            vision_text = _extract_pdf_with_vision(
                file_bytes, document=document, feature=feature, user=user
            )
        except Exception as exc:
            logger.warning("extraction: pdf-vision failed for %s: %s", document.file_path, exc)
            vision_text = ""
        if vision_text:
            return vision_text, "pdf_vision_haiku"

        # Vision muette ou indisponible (pas de clé : `_extract_pdf_with_vision`
        # rend "" sans appeler personne). Un texte à 99 % juste vaut mieux que
        # rien — mais il se **dit** dégradé plutôt que de passer pour du pypdf
        # propre : un texte faux qu'on croit bon ne se corrige jamais.
        if text:
            return text, "pypdf_lossy"
        return "", "pdf_vision_empty"

    return "", "skipped"


__all__ = ["extract_text", "VISION_MODEL"]
