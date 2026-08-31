"""Root pytest fixtures.

The suite runs with ``--nomigrations`` (see pytest.ini): migrations never run, so
the schema is synced directly from the models and our migration that enables the
pgvector ``vector`` extension (agent/0008) is skipped. ``agent.EmbeddingChunk``
has a ``vector`` column, so the type must exist *before* the test-database schema
is built.

We ensure it from ``django_db_modify_db_settings`` (pytest-django runs it *before*
``django_db_setup`` builds the schema) by creating the extension in two places,
covering both DB-provisioning paths:

- **``template1``** — locally, ``--create-db`` creates a fresh test DB by cloning
  ``template1``, so the clone inherits the extension.
- **the target test DB itself** — in CI the DB already exists (the postgres image
  provisions ``POSTGRES_DB``), so it is *not* re-cloned; we add the extension
  directly. Missing-DB errors are ignored (the template1 path covers that case).

This is the ``--nomigrations`` counterpart of agent/0008 (and mirrors what
apps/agent/tests/conftest.py does post-setup for ``unaccent``).

Ce fichier porte aussi le **caviardage des rapports d'échec** — voir
``pytest_runtest_makereport`` en bas. Un test qui rougit ne doit pas publier
l'environnement dans lequel il tournait.
"""
import os
import re

import pytest


def _create_vector_extension(host, port, user, password, dbname):
    import psycopg

    params = {
        "host": host or "localhost",
        "port": str(port or "5432"),
        "user": user,
        "password": password,
        "dbname": dbname,
    }
    conninfo = " ".join(f"{k}={v}" for k, v in params.items() if v)
    try:
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except psycopg.OperationalError:
        # DB doesn't exist yet (it will be cloned from template1) — fine.
        pass
    except (psycopg.errors.UniqueViolation, psycopg.errors.DuplicateObject):
        # Deux workers xdist ont assuré l'extension sur la *même* base au même
        # instant — `template1`, que tous partagent. `IF NOT EXISTS` ne protège
        # pas de ça : les deux la voient absente, les deux insèrent, l'un perd
        # sur `pg_extension_name_index`. Ce qu'on demandait est vrai quand même
        # (l'extension existe), donc perdre la course n'est pas un échec.
        pass


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings):
    from django.conf import settings

    default = settings.DATABASES.get("default", {})
    if "postgresql" not in default.get("ENGINE", ""):
        return django_db_modify_db_settings

    host = default.get("HOST")
    port = default.get("PORT")
    user = default.get("USER")
    password = default.get("PASSWORD")
    test_name = (default.get("TEST") or {}).get("NAME") or f"test_{default.get('NAME')}"

    for dbname in ("template1", test_name):
        _create_vector_extension(host, port, user, password, dbname)

    return django_db_modify_db_settings


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Vide le cache entre deux tests — sinon les compteurs de débit fuient.

    Depuis que `DEFAULT_THROTTLE_CLASSES` pose un plancher, **toute** requête de
    la suite incrémente un compteur, et `LocMemCache` survit d'un test à l'autre
    dans un même process. Sans ce vidage, un fichier de tests qui envoie
    quelques centaines de requêtes finit par en faire refuser une : l'échec
    tombe alors sur un test **innocent**, choisi par l'ordre d'exécution, ce qui
    est la forme la plus coûteuse de test instable.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


# --------------------------------------------------------------------------- #
# Caviardage des rapports d'échec
# --------------------------------------------------------------------------- #
#
# Constaté en écrivant le garde-fou de nom de dépôt : une assertion portant
# directement sur `os.environ.get("…")` fait introspecter la table **entière** par
# pytest, qui l'imprime dans le rapport d'échec. La sortie contenait un
# `GITLAB_PRIVATE_TOKEN` exporté depuis `~/.zshrc` — un jeton qui n'a rien à voir
# avec ce projet, hérité par tout processus lancé depuis le shell.
#
# Sur ce dépôt **public**, ce rapport part dans un log GitHub Actions lisible par
# n'importe qui. Et le chemin n'était surveillé par rien : `gitleaks` scanne les
# commits, pas la sortie des tests.
#
# Le site fautif a été corrigé, mais corriger un site ne ferme pas la famille :
# n'importe quel `assert` futur sur un mapping d'environnement, un objet de
# configuration ou une réponse HTTP peut rouvrir le trou, et **en revue le diff
# fautif ressemble exactement au diff juste**. D'où ce filet, qui ne dépend
# d'aucune discipline d'écriture.

_SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|PRIVATE_KEY|"
    r"ACCESS_KEY|AUTH|DSN|SENTRY|VAPID|_KEY)",
    re.IGNORECASE,
)

# Préfixes de jetons connus, pour ce qui ne vient pas de l'environnement (lu dans
# un fichier, forgé dans une fixture). Le filet ne peut pas tout voir — ces
# motifs couvrent les émetteurs que ce projet croise réellement.
_SECRET_SHAPES = re.compile(
    r"\b("
    r"glpat-[A-Za-z0-9._-]{8,}"          # GitLab
    r"|gh[pousr]_[A-Za-z0-9]{16,}"       # GitHub (classique)
    r"|github_pat_[A-Za-z0-9_]{16,}"     # GitHub (fine-grained)
    r"|sk-ant-[A-Za-z0-9._-]{16,}"       # Anthropic
    r"|npm_[A-Za-z0-9]{16,}"             # npm
    r"|pk_[A-Za-z0-9]{8,}\.[A-Za-z0-9._-]{8,}"  # Voyage
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"  # JWT
    r")",
)

_REDACTED = "<caviardé par conftest>"

# Valeurs trop courtes ou trop communes : les caviarder ferait plus de bruit que
# de bien (`DEBUG=1`, `AUTH=none`), et un secret de 7 caractères n'en est pas un.
_MIN_SECRET_LENGTH = 8


def _secret_values():
    """Les valeurs réellement présentes dans l'environnement, à caviarder.

    Lu à chaque appel plutôt que mémoïsé : un test peut poser une variable via
    `monkeypatch.setenv`, et c'est justement le genre de valeur qu'on ne veut pas
    voir ressortir.
    """
    return {
        value
        for name, value in os.environ.items()
        if _SECRET_NAME.search(name) and len(value) >= _MIN_SECRET_LENGTH
    }


def _redact(text):
    """Rend `text` publiable, et dit s'il a fallu y toucher."""
    cleaned = text
    for value in sorted(_secret_values(), key=len, reverse=True):
        cleaned = cleaned.replace(value, _REDACTED)
    cleaned = _SECRET_SHAPES.sub(_REDACTED, cleaned)
    return cleaned, cleaned != text


def _scrub(report):
    """Remplace le rapport d'échec par sa version caviardée, si nécessaire.

    Le remplacement dégrade un `longrepr` riche en texte brut (plus de couleurs,
    plus de surlignage de la ligne fautive), donc il n'a lieu **que** si un
    secret a été trouvé. Un échec ordinaire garde toute sa lisibilité ; seuls les
    rapports qui fuient sont dégradés, et pour ceux-là c'est le bon échange.
    """
    if not getattr(report, "longrepr", None):
        return
    try:
        text = report.longreprtext
    except (AttributeError, UnicodeDecodeError):  # longrepr exotique
        return
    cleaned, touched = _redact(text)
    if touched:
        report.longrepr = cleaned


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    _scrub(report)
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector):
    # Le hook qui **produit** le rapport de collecte, pas `pytest_collectreport`
    # qui ne fait que le recevoir : un wrapper posé sur celui-là caviarderait
    # après que le reporter de terminal l'a déjà lu.
    report = yield
    _scrub(report)
    return report
