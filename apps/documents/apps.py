from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'

    def ready(self):
        import documents.signals  # noqa: F401

        from agent.searchables import SearchableSpec, register
        from core.visibility import (
            PrivacySpec,
            register as register_privacy,
            visible_to_creator,
        )
        from .models import Document

        # Confidentialité — la déclaration vit ici, une seule fois, et vaut pour
        # toutes les portes de lecture (liste REST, palette ⌘K, agent, contexte
        # ancré). Voir ``core.visibility``.
        register_privacy(PrivacySpec(model=Document, narrow=visible_to_creator))

        register(SearchableSpec(
            entity_type='document',
            model=Document,
            search_fields=('name', 'notes', 'ocr_text'),
            label_attr='name',
            url_template='/app/documents/{id}',
            # Même règle que `views.get_documents_queryset_for_request` : un
            # document privé n'appartient qu'à son déposant. Sans cette ligne, le
            # foyer était le seul filtre du retrieval et l'OCR d'une pièce privée
            # était citable par tout le monde.
        ))
