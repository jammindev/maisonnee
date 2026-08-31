from django.apps import AppConfig


def _project_related(project):
    """Every household item linked to a project, for the `get_related` agent tool.

    Walks the reverse relations to gather the project's expenses / interactions,
    tasks and zones. Linked documents are added centrally by
    ``agent.related.gather_related``. Each returned instance is turned into a
    citable Hit through its own registered spec (unregistered types are skipped).
    Interactions are linked via the polymorphic source FK, not a reverse relation.
    """
    from django.contrib.contenttypes.models import ContentType
    from interactions.models import Interaction

    items = []
    items.extend(
        Interaction.objects.filter(
            source_content_type=ContentType.objects.get_for_model(type(project)),
            source_object_id=project.pk,
        )
    )
    items.extend(project.tasks.all())
    items.extend(pz.zone for pz in project.project_zones.select_related("zone"))
    return items


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projects"

    def ready(self):
        from agent.searchables import SearchableSpec, register
        from .models import Project

        register(SearchableSpec(
            entity_type='project',
            model=Project,
            search_fields=('title', 'description'),
            label_attr='title',
            url_template='/app/projects/{id}',
            related=_project_related,
        ))

        # Capacité optionnelle (parcours 32, lot 1) — la création assistée d'un
        # chantier. L'app qui possède l'écran possède sa déclaration :
        # `app_settings` ne connaît pas la liste.
        #
        # La **clé** est distincte d'`assistant` bien que la condition soit la
        # même, et il faut résister à l'envie de les fondre : « l'assistant ne
        # peut pas répondre » et « les projets se créent au formulaire » ne
        # disent pas la même chose à qui lit l'écran, et c'est exactement le
        # malentendu que le registre existe pour supprimer. Elles ne se couperont
        # pas ensemble non plus le jour où le module `agent` se désactive par
        # foyer — un entretien n'est pas une conversation.
        #
        # Le **prédicat**, lui, est importé et non recopié : « un modèle peut-il
        # répondre sur cette instance » n'a qu'une définition.
        from agent.capabilities import assistant_available
        from app_settings.capabilities import CapabilitySpec, register as register_capability

        register_capability(CapabilitySpec(
            key="project_assistant",
            available=assistant_available,
            doc_anchor="assistant-anthropic",
            env_vars=("ANTHROPIC_API_KEY",),
        ))
