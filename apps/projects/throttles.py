"""Le seul geste des projets qui coûte de l'argent — donc le seul à part.

Le plancher global (`core.throttles`) borne des **requêtes** : il compte pareil
un `GET /api/projects/` et un tour d'entretien, alors que le second achète un
appel au fournisseur. C'est la règle du `CLAUDE.md` — *ce qui coûte de l'argent
se borne à part de ce qui coûte une requête* — la même qui a produit
`document_upload`, `ocr_reprocess` et `hunt_riddles`.

Le cap se lit en **entretiens**, pas en requêtes : un entretien vaut jusqu'à sept
appels (six questions plus le plan). Soixante par heure laissent largement la
place à quelqu'un qui recommence deux ou trois fois pour ajuster le résultat ; un
onglet resté ouvert sur une boucle, non.
"""
from rest_framework.throttling import UserRateThrottle


class ProjectAssistantThrottle(UserRateThrottle):
    """60 tours d'entretien par heure et par utilisateur — environ 8 chantiers."""

    scope = "project_assistant"
