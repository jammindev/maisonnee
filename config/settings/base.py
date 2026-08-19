# config/settings/base.py
"""
Base settings for house backend.
"""
from pathlib import Path
import sys

import environ
from pillow_heif import register_heif_opener

register_heif_opener()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "apps"

if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

# Core settings
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_vite",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    # House apps
    "core",
    "accounts",
    "households",
    "zones",
    "documents",
    "interactions",
    "directory",
    "tags",
    "equipment",
    "stock",
    "electricity",
    "water",
    "weather",
    "projects",
    "insurance",
    "tasks",
    "trackers",
    "photos",
    "app_settings",
    "notifications",
    "alerts",
    "agent",
    "ai_usage",
    "telegram",
    "releases",
    "chickens",
    "orchard",
    "games",
    "pings",
    "budget",
    "recap",
    "banking",
    "shopping",
    "briefings",
    "webpush",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Langue : après AuthenticationMiddleware pour avoir accès à request.user
    "core.middleware.UserLocaleMiddleware",
    "core.middleware.ActiveHouseholdMiddleware",
    "core.middleware.DeviceTokenScopeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.app_debug_admin_link",
                "core.context_processors.active_household_context",
            ],
        },
    },
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("es", "Español"),
]
LOCALE_PATHS = [
    BASE_DIR / "locale",
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Login URLs
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "app_dashboard"
LOGOUT_REDIRECT_URL = "login"

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Custom static files (compiled React components)
]
# ⚠️ `STATICFILES_STORAGE` vivait ici et **ne faisait rien depuis Django 5.1**,
# qui l'a supprimé au profit de `STORAGES`. Le réglage avait donc l'air d'être en
# place et ne l'était pas : le bundle React partait brut, 900 Ko à chaque visite
# froide. Derrière Nginx ça se voyait peu (`gzip on` le recompressait à la
# volée) ; dans une pile auto-hébergée, qui n'a pas de Nginx, ça se voit tout de
# suite — et c'est la première seconde de quelqu'un qui essaie le produit.
#
# `CompressedStaticFilesStorage` et pas `CompressedManifest…` : les noms de
# fichiers portent déjà l'empreinte que Vite y met, donc le manifeste de Django
# n'ajouterait qu'un second schéma de nommage par-dessus le premier — et
# django-vite lit le sien. On veut la compression, pas le renommage.
#
# La compression se fait au `collectstatic`, donc **au build de l'image** : le
# démarrage n'en porte rien.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ⚠️ Le corollaire du choix ci-dessus, et il coûtait cher tout seul.
#
# WhiteNoise ne met `immutable` que sur ce qu'il **reconnaît** comme empreinté, et
# sa reconnaissance passe par le manifeste de Django : il retire le hash d'un nom
# selon la convention `nom.HASH.ext`, redemande l'URL au storage, et conclut
# « versionné » si le storage la remappe sur le nom haché. Sans manifeste — c'est
# notre cas, exprès — le test échoue toujours, et tout retombe sur le défaut de
# 60 secondes.
#
# Mesuré en production : `main-DIchQxlR.js`, 243 Ko, `cache-control: max-age=60`.
# Un nom de fichier qui porte son empreinte avec un cache d'une minute, c'est le
# bundle retéléchargé chaque minute de navigation — la compression réglée juste
# au-dessus payait 243 Ko au lieu de 824, soixante fois par heure au lieu d'une.
#
# Le réglage est un motif, pas un booléen, et c'est ce qui le rend sûr : il ne
# reconnaît que `…/react/assets/nom-HASH.js|css`, la forme que Vite produit. Les
# icônes, favicons et manifeste PWA vivent dans `static/icons/` et gardent le
# cache court — les figer pour toujours voudrait dire qu'un changement de marque
# n'atteint jamais un navigateur qui a déjà visité.
#
# Le chemin est ancré sur `/react/assets/` et non sur `STATIC_URL` : le préfixe
# statique peut changer selon le déploiement, le dossier de sortie de Vite non.
#
# Corrigé ici et pas dans nginx, alors que c'est nginx qui sert la production :
# une instance auto-hébergée n'a **pas** de nginx, et c'est whitenoise qui répond.
# Un correctif dans le proxy n'aurait réparé que le déploiement de l'auteur.
WHITENOISE_IMMUTABLE_FILE_TEST = r"/react/assets/.+-[A-Za-z0-9_-]{8,}\.(?:js|css)$"

# Media files (user-uploaded content, e.g. avatars)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Qui envoie les octets d'un fichier une fois l'accès accordé — voir
# `core.views_media`. `False` = Django lui-même ; `True` = délégué à Nginx par
# `X-Accel-Redirect`, ce que seul un déploiement avec Nginx devant peut promettre.
# Le défaut prudent est donc `False` : un mécanisme absent doit se déclarer, pas
# se deviner.
PROTECTED_MEDIA_ACCEL = False

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "accounts.authentication.DeviceTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Plancher appliqué à toute vue qui ne déclare pas ses propres classes — voir
    # `apps/core/throttles.py` pour le pourquoi. Une vue qui en déclare
    # **remplace** cette liste : les caps serrés de l'agent et de la connexion
    # restent seuls maîtres chez eux.
    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttles.GlobalUserBurstThrottle",
        "core.throttles.GlobalUserSustainedThrottle",
        "core.throttles.GlobalAnonThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Plancher global — large à dessein : un humain ne l'atteint pas, un
        # script emballé oui.
        "user_burst": "240/min",
        "user_sustained": "3000/hour",
        "anon": "120/hour",
        "login_ip": "20/min",
        "login_email": "5/min",
        "signup": "5/hour",
        "change_password": "5/hour",
        "password_reset": "3/hour",
        "invitation_join": "20/hour",
        "agent_burst": "10/min",
        "agent_sustained": "100/hour",
        "search": "120/min",
        # L'envoi d'un document non-photo déclenche un appel de vision
        # **synchrone** (`documents/views.py::_run_extraction`) : ce cap borne
        # une facture, pas seulement un disque.
        "document_upload": "120/hour",
        "ocr_reprocess": "20/hour",
        # Écrire les énigmes d'une chasse est un appel au modèle : on compose
        # une fois, on ajuste deux ou trois fois, on joue.
        "hunt_riddles": "20/hour",
        # Un tour d'entretien de création de projet vaut un appel au modèle, et
        # un entretien complet en vaut jusqu'à sept (six questions + le plan) :
        # le cap se lit en chantiers, pas en requêtes.
        "project_assistant": "60/hour",
    },
}

# Cache — partagé entre les workers, et c'est structurant.
#
# DRF compte les débits dans `django.core.cache`. Le défaut de Django est
# `LocMemCache`, c'est-à-dire **un compteur par process** : avec quatre workers
# gunicorn (voir le `Dockerfile`), « 5 tentatives de connexion par minute » en
# autorisait vingt, « 100 questions à l'agent par heure » quatre cents, et tout
# repartait à zéro à chaque deploy. Les limites n'étaient pas fausses de peu :
# elles étaient fausses d'un facteur égal au nombre de workers, sans que rien ne
# le signale.
#
# La table de cache vit dans Postgres (migration `core.0003`) plutôt que dans un
# service de plus : elle est déjà sauvegardée avec le reste, elle ne coûte pas de
# RAM sur une machine qui n'en a plus, et le volume d'écritures d'un foyer est
# sans commune mesure avec ce qu'une table Postgres encaisse. Passer à Redis un
# jour ne demande que de changer ces lignes.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {
            # Un compteur de débit par (utilisateur, portée) : le défaut de 300
            # purgerait des compteurs vivants dès quelques dizaines de comptes,
            # ce qui **desserre** la limite en silence.
            "MAX_ENTRIES": 20000,
        },
    }
}

# Inscription ouverte — l'auto-hébergeur en a besoin, l'instance de l'auteur non.
#
# `POST /api/accounts/users/` est en `AllowAny` : c'est la seule façon pour
# quelqu'un qui vient de lancer `docker compose up` de créer son premier compte.
# Sur une instance publique déjà en service, c'est une porte ouverte. Le réglage
# distingue les deux cas sans forker le code, et il est **ouvert par défaut**
# parce que le cas nominal du projet est l'auto-hébergement : une instance neuve
# doit s'installer sans lire un guide, celle qui héberge déjà des foyers pose
# `ALLOW_OPEN_SIGNUP=False` dans son `.env`.
ALLOW_OPEN_SIGNUP = True

# Instance de démonstration — le raisonnement complet est dans `production.py`.
# Éteinte par défaut : une instance qui ne pose pas ces variables n'affiche rien
# de tout ça, et c'est le cas de tout auto-hébergeur.
DEMO_MODE = False
DEMO_EMAIL = ""
DEMO_PASSWORD = ""

SPECTACULAR_SETTINGS = {
    "TITLE": "House API",
    "DESCRIPTION": "OpenAPI schema for House Django REST API.",
    "VERSION": "1.0.0",
}

ENABLE_API_SCHEMA = False

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5174",
]
CORS_ALLOW_CREDENTIALS = True

# URL of the frontend SPA — used to build links in transactional emails (password reset, etc.).
# Overridden per environment in local.py / production.py.
FRONTEND_URL = "http://localhost:5174"
DEFAULT_FROM_EMAIL = "noreply@house.local"

# Un e-mail part dans les logs par défaut, pas vers un SMTP. Le défaut de Django
# est `smtp.EmailBackend` sur `localhost:25` : sur une instance sans serveur mail
# — le cas d'un foyer auto-hébergé — chaque envoi partait en timeout au moment de
# l'envoi, loin de l'écran qui l'avait promis. Chaque environnement pose le sien
# (production lit `EMAIL_BACKEND`, les tests `locmem`) ; celui-ci est le filet.
# La capacité `email` du registre (`app_settings.capabilities`) sait que ce
# backend ne délivre rien et le **dit** à l'interface, au lieu de le taire.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Anthropic API key for the AI layer (Claude Vision OCR, agent, ...).
# Empty string by default — extraction degrades to a no-op when unset.
# Overridden per environment in local.py / production.py.
ANTHROPIC_API_KEY = ""

# LLM provider configuration. The agent and OCR layers go through the
# `apps.agent.llm.get_llm_client()` factory keyed on `LLM_PROVIDER`.
# Adding `OllamaClient` later means setting `LLM_PROVIDER=ollama` — no refactor
# needed in the agent or document apps.
LLM_PROVIDER = "anthropic"
LLM_TEXT_MODEL = "claude-haiku-4-5-20251001"
LLM_VISION_MODEL = "claude-haiku-4-5-20251001"
LLM_REQUEST_TIMEOUT_SECONDS = 30
# Vision OCR (full-page images) is slower than chat round-trips.
LLM_VISION_TIMEOUT_SECONDS = 60

# Embedding provider (hybrid semantic retrieval, parcours 21). Anthropic has no
# embeddings API, so vectors come from a separate provider behind
# `apps.agent.embeddings.get_embedding_client()`, keyed on `EMBEDDING_PROVIDER`.
# Prod default: Voyage AI (hosted, 0 GB RAM on the VPS). Ollama local (bge-m3) is
# the target once the machine has >= 8 GB RAM — flip EMBEDDING_PROVIDER=ollama,
# no refactor. See docs/fiches/EMBEDDINGS.md.
EMBEDDING_PROVIDER = "voyage"
EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_REQUEST_TIMEOUT_SECONDS = 30
# Ollama endpoint, only used when EMBEDDING_PROVIDER=ollama.
EMBEDDING_BASE_URL = "http://localhost:11434"
# Provider API keys — empty by default; set per environment / in .env.
# EMBEDDING_PROVIDER selects which one is used (voyage | openai | ollama).
VOYAGE_API_KEY = ""
OPENAI_API_KEY = ""
# Write-time indexing: when True, post_save/post_delete of a searchable entity
# (re)builds its EmbeddingChunk rows synchronously (best-effort). Off by default
# so tests and provider-less setups incur no side effect; enable via env once
# VOYAGE_API_KEY is set (aligns with activating hybrid retrieval, parcours 21).
# The backfill command indexes regardless of this flag.
EMBEDDING_INDEXING_ENABLED = False

# Hybrid retrieval (parcours 21 lot 3): when True, `retrieval.search()` adds a
# semantic (pgvector k-NN) leg alongside full-text and fuses both with Reciprocal
# Rank Fusion. Off by default → byte-identical to pure full-text. Turn on only
# once the index is populated (VOYAGE_API_KEY set + `backfill_embeddings` run).
AGENT_HYBRID_RETRIEVAL_ENABLED = False
# RRF damping constant (rank fusion). 60 is the standard default.
RRF_K = 60

# Agent tool-use loop: max LLM round-trips per question. Each iteration is one
# LLM call; the tools are dropped on the last pass to force a final answer.
# Bounds latency and cost of the function-calling loop. 4 leaves room to chain
# search_household -> get_entity -> answer in a single turn.
AGENT_MAX_TOOL_ITERATIONS = 4

# Agent conversation retention: conversations untouched for longer than this are
# eligible for cleanup by `manage.py cleanup_agent_conversations`. 0 disables it.
AGENT_CONVERSATION_RETENTION_DAYS = 365

# Agent web search (Anthropic server-side `web_search` tool). Off by default: it
# calls the public web (cost + external content) and its dynamic result filtering
# requires the agent to run on Sonnet 4.6+ (set LLM_TEXT_MODEL accordingly).
# When ON, the model may search the web for current/external facts it can't
# answer from household data or stable general knowledge. `MAX_USES` caps the
# number of searches per question (0 = no cap).
AGENT_WEB_SEARCH_ENABLED = False
AGENT_WEB_SEARCH_MAX_USES = 5

# Proactive daily digest (parcours 19). The digest reuses the pings scheduler +
# Telegram delivery; these tune its content and optional polish.
# - ELEC_ANOMALY_THRESHOLD: relative increase (last 30d vs previous 30d) above
#   which the electricity section fires (0.30 = +30%).
# - AI_POLISH_ENABLED: when on (and an API key is set), the digest text is
#   rewritten by the LLM into a warm paragraph; any failure falls back to the
#   deterministic template. Off by default (cost + keeps the send deterministic).
DIGEST_ELEC_ANOMALY_THRESHOLD = 0.30
DIGEST_AI_POLISH_ENABLED = False

# Budgets (parcours 21): ratio at which a monthly budget flips to the "attention"
# state (below the 100% overrun). 0.8 = warn once 80% of the ceiling is spent.
# --- Banking auto-reconciliation (parcours 25 lot 6) ---
# A card is debited after the purchase, but users sometimes record a day late,
# hence an asymmetric window.
BANKING_MATCH_WINDOW_BEFORE_DAYS = 7
BANKING_MATCH_WINDOW_AFTER_DAYS = 3
# Auto-linking also requires a strictly equal amount and a clear winner: an
# approximate match becomes a suggestion, never a silent link.
BANKING_MATCH_AUTO_THRESHOLD = 0.85
BANKING_MATCH_SUGGEST_THRESHOLD = 0.55

BUDGET_WARNING_RATIO = 0.8

# Monthly budget report (lot 3): when on + an API key exists, the factual report
# is rewritten into a warm paragraph by the LLM (fallback = deterministic text).
BUDGET_REPORT_AI_POLISH_ENABLED = False

# --- Household monthly recap (parcours 27) ---
# MIN_CARDS: below this many cards the recap is still computed and browsable, but
# no ping is sent and no dashboard teaser appears — a monthly appointment that
# delivers nothing wears the appointment out.
# AI_POLISH_ENABLED: when on + an API key exists, the factual captions (never the
# figures) are rewritten into warmer one-liners. Off by default, same reason as the
# digest and the budget report: the deterministic template must always leave.
RECAP_MIN_CARDS = 3
RECAP_AI_POLISH_ENABLED = False

# Telegram bot channel for the agent. Empty token = channel disabled: the
# webhook rejects everything and no outbound call is ever made.
# Overridden per environment in local.py / production.py.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_BOT_USERNAME = ""  # public @username of the bot, for t.me deep-links
# --- Web Push (VAPID) -------------------------------------------------------
# Empty by default → push is a clean no-op (see webpush.service.is_configured).
# Generate a pair with `python manage.py generate_vapid_keys`, set them per
# environment (local.py / production.py via .env). VAPID_PUBLIC_KEY is the
# base64url application server key the browser needs; VAPID_ADMIN_EMAIL is the
# `mailto:` contact required by the push services.
VAPID_PUBLIC_KEY = ""
VAPID_PRIVATE_KEY = ""
VAPID_ADMIN_EMAIL = ""
TELEGRAM_WEBHOOK_SECRET = ""
TELEGRAM_LINK_TOKEN_MAX_AGE_SECONDS = 15 * 60
# Per-chat cooldown between agent questions — a burst of messages costs one
# LLM call, the rest get a "slow down" reply.
TELEGRAM_COOLDOWN_SECONDS = 5
