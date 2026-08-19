#!/usr/bin/env bash
#
# Remise à zéro de l'instance de démonstration.
#
# La démo est **modifiable** : un visiteur qui ne peut rien changer ne sait pas
# ce que ça fait de s'en servir. Le prix, c'est qu'elle se dégrade — des lignes
# saisies au hasard, des choses supprimées. D'où ce script, appelé par le timer
# systemd utilisateur `maisonnee-demo-reset.timer` (unités versionnées dans
# `systemd/`). **Ce VPS n'a pas de cron** : `crontab` n'y est pas installé, et
# chercher à l'utiliser fait perdre une heure — voir DEPLOYMENT.md § 11.
#
# Deux choses à savoir avant de toucher à la cadence :
#
#   - `seed_demo_data --flush` est borné au foyer « Famille Mercier ». Il ne peut
#     pas toucher autre chose, et il n'y a rien d'autre sur cette instance.
#   - Les embeddings sont posés par un signal `post_save`. Semer signal allumé,
#     c'est ~650 appels unitaires au fournisseur chaque nuit ; on l'éteint et on
#     rattrape en lots avec `backfill_embeddings`.
#
# Le script fait donc DEUX choses, et la seconde est facile à oublier : il remet
# les données à zéro, et il **rattrape la dernière release publiée**. C'est le seul
# mécanisme qui met la vitrine à jour — aucun workflow ne s'en charge.
#
# La cadence vit dans `systemd/maisonnee-demo-reset.timer`, pas ici — un
# `OnCalendar=` à changer si un jour d'annonce la démo se dégrade avant midi, suivi
# d'un `systemctl --user daemon-reload`. Voir DEPLOYMENT.md § 11.
set -euo pipefail

cd "$(dirname "$0")"

# `--flush` recrée aussi les trois comptes, donc le mot de passe doit être
# repassé : sans lui la commande retomberait sur celui, publié, du dépôt.
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "[$(date -Is)] remise à zéro de la démonstration"

# ── Rattraper la dernière release, AVANT de resemer ─────────────────────────
#
# La vitrine consomme le paquet publié (`ghcr.io/...:latest`), pas les sources —
# c'est ce qui l'empêche de montrer des fonctionnalités qu'une installation ne
# donnerait pas. La contrepartie est qu'elle ne bouge qu'aux releases, et rien
# dans la CI ne la met à jour : ce `pull` est le seul mécanisme qui l'y amène.
#
# ⚠️ Les deux commandes comptent, et le `pull` seul serait un demi-correctif.
# La seed exécutée plus bas est **le code de l'image**, lancé par `exec` dans le
# conteneur DÉJÀ démarré : tirer une image neuve sans recréer le conteneur ferait
# tourner l'ancienne seed indéfiniment, en donnant l'impression de se mettre à
# jour. `up -d` ne recrée que si l'image a réellement changé.
docker compose pull --quiet

# Migrer AVANT de basculer, sur un conteneur jetable de l'image neuve — même ordre
# qu'en production. Sans cette étape, la seed d'une release qui ajoute une app tape
# sur des tables absentes : `relation "games_hunts" does not exist`, constaté en
# passant la démonstration de la v0.3.0 à la v0.4.0 et ses sept migrations.
docker compose run --rm --no-deps web python manage.py migrate --noinput

# ⚠️ `--force-recreate`, et ce n'est pas de la prudence excessive : Compose compare
# le **nom** de l'image du service, pas le digest résolu. Le tag `latest` ne change
# jamais de nom, donc `up -d` seul considère le conteneur à jour et ne le recrée
# pas — l'ancienne image continue de tourner. Mesuré : image locale à jour, digest
# neuf dans le registre, et la seed qui produisait encore 20 opérations au lieu de
# 619.
#
# Recréer chaque nuit coûte quelques secondes sur une instance qu'on efface de
# toute façon, et supprime toute une classe de panne silencieuse : « la démo a
# l'air à jour et ne l'est pas » est exactement ce qu'on ne veut pas pouvoir dire.
docker compose up -d --force-recreate --wait --wait-timeout 180 --no-deps web

docker compose exec -T \
  -e EMBEDDING_INDEXING_ENABLED=0 \
  web python manage.py seed_demo_data --flush --password "${DEMO_PASSWORD}"

# Même garde que dans le compose : la commande lève si la clé est absente, et le
# `set -e` ferait échouer l'unité chaque nuit sur une capacité facultative — alors
# que la remise à zéro, elle, a parfaitement réussi.
if [ -n "${VOYAGE_API_KEY:-}" ]; then
  docker compose exec -T web python manage.py backfill_embeddings
else
  echo "[$(date -Is)] VOYAGE_API_KEY absente : indexation sémantique ignorée"
fi

echo "[$(date -Is)] terminé"
