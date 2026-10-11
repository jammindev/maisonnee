"""Une sonde de santé qui ne peut pas réussir éteint la vitrine sans rien dire.

Le 18 août, `deploy/demo/docker-compose.yml` a gagné un healthcheck sur `/health/`
pour que le `--wait` de `reset.sh` attende gunicorn et non le seul démarrage du
conteneur. La sonde interrogeait `http://127.0.0.1:8000/health/` — donc avec
`Host: 127.0.0.1:8000`, que `ALLOWED_HOSTS` refuse en **400 DisallowedHost**.

L'application allait parfaitement bien : elle déclinait la sonde au nom de sa
propre sécurité, laquelle fonctionnait. Mais un conteneur `unhealthy` fait tomber
**deux** choses à la fois, et c'est ce cumul qui a coûté douze jours :

1. **Traefik ignore les conteneurs `unhealthy`.** Le routeur quitte sa table, et le
   domaine public répond 404 — le 404 de Traefik lui-même (`text/plain`, 19 octets,
   routeur `"-"` dans son log d'accès), pas une erreur de l'app. Rien dans les logs
   applicatifs ne le signale, puisque l'app n'est jamais atteinte.
2. **`reset.sh` échoue** sur son `up -d --wait` (`container demo-web-1 is
   unhealthy`), donc la remise à zéro nocturne cesse aussi. La vitrine était donc
   injoignable *et* figée sur des données de douze jours.

**Pourquoi un test et pas une relecture.** Le défaut ne se déclenche qu'à la
**recréation** du conteneur : il est passé vert en CI, vert au merge, et il a dormi
jusqu'au premier deploy suivant — bien après que quiconque ait regardé le diff. Et
en revue, une sonde HTTP sans en-tête `Host` ressemble exactement à une sonde
correcte : il n'y a rien de visiblement manquant, il faut *savoir* que Django
valide l'hôte. C'est la signature du travail à sortir de l'espace latent.

**Portée.** Ce test ne lance pas Docker — il lit le fichier. La propriété vérifiée
est statique et suffisante : *toute sonde qui parle HTTP à l'application doit
présenter un `Host` que l'application accepte.* Elle se lit dans la source, comme
la taille de police de `field-font-size.test.ts`.
"""
import re
from pathlib import Path

import pytest
import yaml
from django.conf import settings

#: Tous les composes qui lancent l'application. **La prod y est aussi** : elle
#: portait déjà la bonne sonde, mais rien ne la tenait — et c'est justement parce
#: que personne ne comparait les deux fichiers que la version fautive a pu être
#: écrite à côté de la version juste.
COMPOSE_FILES = (
    "docker-compose.prod.yml",
    "deploy/demo/docker-compose.yml",
)

#: Les composes dont le service `web` est **directement** derrière Traefik. En prod
#: c'est `nginx` qui porte les labels et `web` qui vit derrière lui : exiger une
#: règle Traefik sur `web` y serait faux, pas strict.
TRAEFIK_FRONTED = ("deploy/demo/docker-compose.yml",)

#: Le template d'environnement de chaque compose. Explicite, parce que le deviner
#: « à côté du fichier » est faux : à la racine, `.env.example` est celui du **dev
#: local** (`ALLOWED_HOSTS=127.0.0.1,localhost`, aucun `DOMAIN`) et le template de
#: production est `.env.production.example`. Une convention devinée aurait fait
#: échouer le test sur un fichier correct.
ENV_EXAMPLES = {
    "docker-compose.prod.yml": ".env.production.example",
    "deploy/demo/docker-compose.yml": "deploy/demo/.env.example",
}

#: Les services dont la sonde interroge **l'application Django**. `db` fait un
#: `pg_isready`, qui ne passe par aucun contrôle d'hôte : l'exiger de lui rendrait
#: le test faux plutôt que strict.
DJANGO_SERVICES = ("web",)


def _compose(relative: str) -> dict:
    raw = (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")
    return yaml.safe_load(raw)


def _healthcheck_command(service: dict) -> str:
    """La commande de la sonde, aplatie en une chaîne quelle que soit sa forme."""
    test = (service.get("healthcheck") or {}).get("test")
    if test is None:
        return ""
    return " ".join(test) if isinstance(test, list) else str(test)


@pytest.mark.parametrize("relative", COMPOSE_FILES)
@pytest.mark.parametrize("service_name", DJANGO_SERVICES)
def test_an_http_probe_presents_a_host_the_app_accepts(relative, service_name):
    """Une sonde HTTP sur l'app porte un `Host`, et c'est celui du domaine servi."""
    service = _compose(relative)["services"][service_name]
    command = _healthcheck_command(service)

    assert command, (
        f"{relative} :: {service_name} n'a aucun healthcheck. Le `--wait` de "
        "`reset.sh` n'attendrait alors que le démarrage du conteneur, pas gunicorn."
    )

    if not re.search(r"https?://", command):
        return  # sonde non-HTTP : hors périmètre, elle ne traverse pas ALLOWED_HOSTS

    assert "Host" in command, (
        f"{relative} :: la sonde de {service_name} fait une requête HTTP sans "
        "en-tête `Host`. Elle partira avec `Host: 127.0.0.1:8000`, que "
        "`ALLOWED_HOSTS` refuse en 400 — le conteneur passera `unhealthy`, Traefik "
        "retirera son routeur et le domaine répondra 404.\n"
        f"  commande : {command}"
    )
    assert "${DOMAIN}" in command, (
        f"{relative} :: la sonde de {service_name} présente un `Host` en dur. Il "
        "doit valoir `${DOMAIN}` — la même variable que la règle Traefik et que "
        "`ALLOWED_HOSTS`, sinon les trois peuvent diverger et c'est la sonde qui "
        "tranchera, en éteignant le site.\n"
        f"  commande : {command}"
    )


def test_every_compose_probes_the_app_the_same_way():
    """Les composes ne s'écartent pas l'un de l'autre sur la sonde.

    C'est le contrôle qui aurait évité la panne, et il n'existait pas. La sonde
    correcte vivait dans `docker-compose.prod.yml`, commentaire d'explication
    compris ; celle de la démonstration a été **réécrite de zéro** trente lignes
    plus loin, donc à nouveau fautive.

    `CLAUDE.md` § « Chercher avant de construire » le dit déjà pour le code :
    « en écrire une dix-septième n'est pas neutre, c'est rouvrir le bug que la
    consolidation a fermé. » Ça vaut aussi pour une ligne de compose — et une
    divergence entre deux fichiers de déploiement ne se voit dans aucun des deux
    diffs, puisque chacun est cohérent tout seul.
    """
    probes = {
        relative: _healthcheck_command(_compose(relative)["services"]["web"])
        for relative in COMPOSE_FILES
    }
    distinct = set(probes.values())
    assert len(distinct) == 1, (
        "les composes sondent l'application différemment — copie la sonde de "
        "`docker-compose.prod.yml` au lieu d'en écrire une nouvelle :\n"
        + "\n".join(f"    {rel} :\n      {cmd}" for rel, cmd in probes.items())
    )


@pytest.mark.parametrize("relative", TRAEFIK_FRONTED)
def test_the_probed_host_is_the_one_traefik_routes(relative):
    """`Host` de la sonde, règle Traefik et `ALLOWED_HOSTS` nomment la même chose.

    Le vrai invariant n'est pas « il y a un en-tête » mais « les trois définitions
    de l'hôte servi n'en font qu'une ». Trois copies d'une même valeur dérivent —
    c'est la règle « un compteur ne peut pas avoir deux définitions », et ici la
    divergence ne se paie pas en chiffre faux mais en site éteint.
    """
    compose = _compose(relative)
    web = compose["services"]["web"]

    labels = web.get("labels") or []
    rules = [str(label) for label in labels if ".rule=Host(" in str(label)]
    assert rules, f"{relative} : aucune règle Traefik `Host()` sur le service web"
    for rule in rules:
        assert "${DOMAIN}" in rule, (
            f"{relative} : la règle Traefik n'utilise pas ${{DOMAIN}} — {rule}"
        )

    assert "${DOMAIN}" in _healthcheck_command(web), (
        f"{relative} : la sonde ne vise pas le même hôte que la règle Traefik"
    )


@pytest.mark.parametrize("relative", COMPOSE_FILES)
def test_the_compose_declares_the_variables_its_probe_needs(relative):
    """Un `${DOMAIN}` non défini rendrait l'en-tête vide, donc la sonde à nouveau
    refusée — et le mode de défaillance serait identique, en plus discret.

    On ne peut pas lire le `.env` d'une instance depuis ici (il n'est pas versionné
    et porte des secrets), mais on peut exiger que le **template livré** le
    documente : c'est lui que l'exploitant copie.
    """
    example = Path(settings.BASE_DIR) / ENV_EXAMPLES[relative]
    assert example.is_file(), f"{example} introuvable — la table ENV_EXAMPLES a dérivé"
    content = example.read_text(encoding="utf-8")
    for variable in ("DOMAIN", "ALLOWED_HOSTS"):
        assert re.search(rf"^{variable}=", content, re.M), (
            f"{example} ne documente pas {variable}, dont la sonde et la règle "
            "Traefik dépendent toutes deux"
        )
