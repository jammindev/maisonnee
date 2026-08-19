# Couche IA — note transverse

Ce document est le chapeau commun aux notes de compatibilité IA déjà rédigées par parcours.

Il factorise les principes, le vocabulaire et les décisions à trancher avant d'attaquer une vraie implémentation. Il ne remplace pas les notes par parcours, il les unifie.

Voir aussi :

- [PARCOURS_07_AGENT_CONVERSATIONNEL.md](../../docs/parcours/PARCOURS_07_AGENT_CONVERSATIONNEL.md) — premier porteur d'implémentation IA (agent conversationnel : lecture via function calling, écriture bornée `create_entity` depuis le lot 8 + extensions futures pour capture conversationnelle et compréhension de documents)
- [PARCOURS_32_RACONTER_UN_CHANTIER.md](../../docs/parcours/PARCOURS_32_RACONTER_UN_CHANTIER.md) — première **production d'objets métier** par le modèle (un projet, des tâches, des notes) plutôt que de texte à lire ; fiche associée : [ENTRETIEN_DIRIGE.md](../fiches/ENTRETIEN_DIRIGE.md)

## Objet

Les deux notes IA actuelles sont parallèles : elles vérifient parcours par parcours que le socle reste compatible avec une future couche IA. Elles convergent sur les mêmes principes mais n'ont jamais été factorisées.

Ce document a trois rôles :

1. exposer une vision unifiée de la couche IA produit
2. figer le vocabulaire commun (provenance, confiance, modes de validation)
3. lister explicitement les décisions transverses à trancher avant implémentation

Tout ce qui est ici l'emporte sur les notes par parcours en cas de divergence.

## Promesse produit unifiée

> Un membre du foyer doit pouvoir capturer, recevoir ou qualifier un élément avec le moins d'effort possible, quel que soit le canal d'entrée, sans perdre la traçabilité de la pièce source ni le contrôle final.

Cette promesse couvre les deux parcours IA :

- parcours 01 : capter un événement à partir d'un message libre, d'un formulaire, ou d'un canal externe
- parcours 02 : comprendre un document entrant et le relier au bon contexte métier

Dans les deux cas, le formulaire web reste un client crédible parmi d'autres canaux d'entrée.

## Principe cible

La couche IA ne remplace jamais le contrat métier.

Elle :

1. reçoit une entrée brute : message libre, document, OCR, email, etc.
2. produit une **proposition structurée** alignée sur les contrats métier existants
3. appelle la même couche de création ou de mise à jour que la saisie manuelle
4. conserve la provenance, le texte brut et le niveau de confiance

Conséquence : aucun chemin parallèle. Une `Interaction` créée par IA passe par le même serializer qu'une `Interaction` créée par formulaire. Un rattachement de document suggéré par IA utilise le même contrat `InteractionDocument` que le rattachement manuel.

## Modèle d'architecture

```
canaux d'entrée                  noyau métier
───────────────                  ──────────────
formulaire web        ─┐
chat IA               ─┤
WhatsApp              ─┤   ┌──> Interaction
email entrant         ─┼───┤
upload document       ─┤   └──> Document + InteractionDocument
OCR pipeline          ─┘
```

Règles structurantes :

- les canaux n'écrivent pas directement en base, ils passent par le service métier
- la couche IA est un **producteur de propositions**, pas un canal d'entrée à part entière
- une proposition IA peut elle-même être issue de n'importe quel canal (WhatsApp + IA, email + IA, upload + OCR + IA)

## Contrat de provenance unifié

Toute proposition IA doit conserver dans `metadata` un sous-objet stable. Ce sous-objet est la fusion factorisée des deux notes existantes.

```jsonc
{
  "ai": {
    "source": "whatsapp" | "email" | "upload" | "photo" | "manual" | "chat",
    "source_message_id": "string?",      // si canal externe identifiable
    "raw_text": "string?",               // texte brut d'origine
    "ocr_engine": "string?",             // si extraction OCR
    "parsed_by": "string",               // identifiant du modèle/version
    "confidence": 0.0,                   // 0.0 à 1.0
    "review_state": "auto" | "needs_review" | "draft" | "rejected",
    "suggestions": {                     // optionnel, parcours 02 surtout
      "type": "string?",
      "links": [],
      "summary": "string?"
    }
  }
}
```

Règles :

- ce sous-objet est **optionnel** pour les créations manuelles, **obligatoire** pour les créations IA
- les champs spécifiques à un parcours vivent sous `ai.suggestions` pour ne pas polluer la racine
- la pièce source (texte, fichier) reste accessible — la proposition IA ne la remplace pas

## Niveaux de confiance et modes de validation

Trois modes uniques, valables pour les deux parcours :

| Confiance | Mode | Comportement |
|-----------|------|--------------|
| Haute | `auto` | création directe, suggestion mise en avant ou pré-remplissage confirmé d'un clic |
| Moyenne | `needs_review` | proposition explicite à valider avant de devenir vérité métier |
| Faible | `draft` | brouillon ou simple aide de lecture, aucun rattachement automatique |

Les seuils précis (par exemple 0.8 / 0.5) ne sont pas figés ici. Ils seront calibrés par parcours dans le design doc d'implémentation.

## Mode `needs_review`

Le besoin d'un état intermédiaire est commun aux deux parcours. Il doit être pensé comme un mécanisme transverse, pas dupliqué entité par entité.

Pistes à instruire dans le design doc d'implémentation :

- ajouter un champ `review_state` partagé sur les entités susceptibles d'être créées par IA (`Interaction`, `Document`, peut-être `InteractionDocument`)
- ou conserver l'état uniquement dans `metadata.ai.review_state` tant qu'aucune requête transversale ne le justifie
- exposer dans l'UI un emplacement clair pour les éléments en attente de revue (file d'attente dédiée ou filtre liste)

Décision : ne pas trancher ici, mais ne pas exclure ce mode par le design actuel.

> **Divergence actée (lot 8 agent, 2026-07)** : pour les écritures de l'agent conversationnel (`create_entity` — tâche, note), le choix retenu est **« créer + Undo »** plutôt que `needs_review` : l'item est créé immédiatement via le service métier, remonté dans `metadata.created_entities`, et annulable d'un clic (toast). Rationale dans [PARCOURS_07_LOT8_ACTIONS_ECRITURE.md](../../docs/parcours/PARCOURS_07_LOT8_ACTIONS_ECRITURE.md) §8 : à l'échelle solo-user, une validation préalable ajoute de la friction sans bénéfice, et l'annulation immédiate offre le même contrôle final. `needs_review` reste le mécanisme cible pour les canaux **asynchrones** (capture WhatsApp/email, compréhension de documents à l'upload), où l'utilisateur n'est pas dans la boucle au moment de la création. Le contrat de provenance `metadata.ai.*` n'est pas encore porté par ces créations — à instruire quand un canal asynchrone l'exigera.

> **Deuxième divergence actée (parcours 32, 2026-08)** : pour une **création en
> lot** — un entretien produit un projet, six tâches, deux notes et une enveloppe
> d'un seul geste — ni `créer + Undo` ni `needs_review` ne conviennent. Douze
> bulles « Annuler » ne sont pas un contrôle, et un état `needs_review` sur douze
> objets fabriquerait une file à vider. Le choix retenu est la **relecture avant
> écriture** : le plan est proposé, édité et décoché à l'écran, et **rien n'est
> écrit** avant validation — deux endpoints distincts, celui qui parle au modèle
> ne connaissant aucune écriture. La règle de bascule est la **cardinalité**, pas
> le principe : `créer + Undo` reste juste pour un objet. Conséquence assumée : la
> provenance `metadata.ai.*` n'est pas portée non plus, la relecture transférant
> la paternité du contenu à celui qui l'a validé.

## Règles à préserver dès maintenant

Pour rester compatible avec une future implémentation IA, les décisions suivantes doivent rester vraies :

1. les règles métier importantes vivent côté backend, pas côté React
2. le payload des entités créables par IA reste simple, stable, et exprimable hors UI
3. `metadata` absorbe les besoins spécifiques tant qu'ils ne justifient pas un vrai champ
4. la provenance d'une création doit pouvoir être conservée sans changer le modèle
5. la pièce source (texte brut, fichier, OCR) reste accessible
6. un futur mode `draft` / `needs_review` ne doit pas être exclu par le design actuel
7. aucun couplage ne lie un parcours à un canal unique

## Ce qu'il ne faut pas faire

- mettre une règle métier seulement dans React
- coupler la création d'`Interaction` au seul formulaire web
- masquer la pièce source d'un document derrière un résumé IA
- stocker des interprétations IA sans trace de provenance ni confiance
- transformer trop tôt une suggestion en vérité métier définitive
- introduire des validations UI impossibles à reproduire côté API

## Hors scope V1

Sont **explicitement hors scope** d'une première itération IA :

- ingestion email entrante comme surface runtime active
- intégration WhatsApp ou autre canal externe en lecture
- compréhension automatique sans confirmation pour les cas à faible confiance
- pipeline OCR avancé (au-delà de ce qui existe déjà)
- décisions IA opaques sans pièce source consultable

Ces sujets restent compatibles avec l'architecture mais ne sont pas livrables tant que le socle IA transverse n'est pas posé.

## Décisions transverses

Décisions tranchées par la livraison V1 du parcours 07 (2026-05-02). Les sujets restant ouverts concernent les extensions IA des parcours 01 et 02.

### Décisions déjà tranchées

#### Provider et modèle

**Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) + SDK officiel `anthropic` pour OCR (Vision) et agent. `pypdf` pour PDFs texte avec fallback Vision multi-page sur PDFs scannés (#107). Tranché dans #88, confirmé pour l'agent dans #101 (validé en prod, latence 2-4s).

#### Sync vs async

**Sync** pour V1, pas de Celery. Tranché dans #88, confirmé sur l'agent. Async réservé aux pièces volumineuses si la sync devient bloquante.

#### Stockage de l'extraction OCR

- texte extrait dans `Document.ocr_text` (champ existant)
- traçabilité dans `metadata` : `ocr_extracted_at`, `ocr_method` (`vision_haiku` | `vision_pages` | `pypdf` | `skipped`)

Tranché dans #88, #89 et #107.

#### Où vit le service IA

- **Lot 0 du parcours 07** : `apps/documents/extraction.py` + `apps/documents/image_processing.py`
- **Lots 1+ du parcours 07** : nouvelle app `apps/agent/` (`searchables.py`, `retrieval.py`, `llm.py`, `service.py`, `prompts.py`, `views.py`)
- **Observabilité IA centralisée** : nouvelle app `apps/ai_usage/` (`AIUsageLog` + `log_ai_usage()`), partagée par toutes les features IA

#### Abstraction LLM

**`LLMClient` Protocol + `AnthropicClient` concret + factory `get_llm_client()` keyed sur `LLM_PROVIDER`** (lot 2 du parcours 07). Permet un futur `OllamaClient` (modèle local) sans réécrire la couche métier. Tranché dans #101.

#### Citations vérifiables

Format `<cite id="entity_type:id"/>` dans la réponse, parsé par regex côté service, **intersecté avec les hits du retrieval** — un marqueur que le LLM invente est ignoré. Invariant : l'agent ne peut pas citer ce qu'on ne lui a pas montré. Tranché dans #101.

#### Mention de confidentialité

Modale Radix non-dismissible au premier usage de l'agent, persistance localStorage `agent.privacyAccepted.v1`, trois points couverts (provider externe, scope household, pas de stockage du contenu des conversations). Tranché dans #102.

#### Audit log des appels IA

Table `AIUsageLog` populated à chaque appel LLM. On stocke métadonnées (feature, provider, model, durée, tokens, success), **pas le contenu** des prompts ou réponses — décision tranchée pour limiter la surface confidentialité. Skeleton livré dans le lot 2, KPIs et UI = lot 6 (#109).

### Décisions encore ouvertes (extensions parcours 01 et 02)

#### Contrat de proposition (parcours 01 et 02)

- Schéma JSON unique pour toutes les propositions IA, ou schéma par type d'entité ?
- Validation côté backend systématique avant de matérialiser une proposition ?
- Comment gérer une proposition partielle (champs manquants ou incertains) ?

#### Stockage des suggestions (parcours 02)

- Recalculées à la demande ou persistées ?
- Si persistées : nouvelle table `AISuggestion` polymorphe, ou champs `metadata.ai.*` sur l'entité cible ?
- Durée de rétention des suggestions rejetées ?

#### Stratégie sur les zones manquantes (parcours 01)

- Zone par défaut implicite type `À classer` ?
- Brouillon obligatoire tant qu'aucune zone n'est résolue ?
- Inférence avec seuil de confiance dédié ?

#### Résolution utilisateur et household (parcours 01)

- Comment un canal externe (chat IA, email, WhatsApp) résout-il l'utilisateur et le household ?
- Création faite au nom de l'utilisateur ou via un compte système assistant ?
- Audit trail correspondant ?

#### Sécurité et confidentialité (à étendre pour multi-user)

Tranché en V1 solo user :
- mention de confidentialité visible avant premier usage agent (modale localStorage)
- audit log structurel via `AIUsageLog` mais sans contenu des prompts/réponses

Reste à arbitrer si on ouvre à d'autres utilisateurs :
- politique de redaction PII avant envoi au modèle
- audit log incluant le contenu des prompts (permet le débogage mais coûte en confidentialité)

## Étape suivante

Le **parcours 07** (agent conversationnel) a livré sa V1 le 2026-05-02 (lots 0a → 3). Le socle IA transverse est posé : pipeline OCR, abstraction `LLMClient`, citations vérifiables, audit log centralisé.

Suite recommandée :

1. **Parcours 07 — lot 6 (#109)** : agrégations + page admin sur `AIUsageLog`. À livrer quand le besoin de quantifier la qualité d'usage se fait sentir.
2. **Extensions IA des parcours 01 et 02** (documentées dans la section "Évolutions ultérieures" de la doc parcours 07) : compréhension assistée de documents puis capture conversationnelle. S'appuient toutes deux sur la couche IA déjà posée — le contrat de proposition et la stratégie multi-canal restent à trancher avant d'attaquer.

L'invariant : ne pas dupliquer la couche IA. Toute nouvelle feature IA passe par `apps.agent.llm.get_llm_client()` et logue dans `AIUsageLog`.
