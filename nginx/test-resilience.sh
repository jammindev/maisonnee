#!/usr/bin/env bash
#
# Test de régression du reverse-proxy — un deploy ne doit jamais montrer un 502.
#
# Trois propriétés, chacune correspondant à une panne constatée en prod
# (issue #449) :
#
#   1. nginx démarre et répond même si `web` n'existe pas encore — et il répond la
#      page de maintenance (503), pas la page d'erreur nginx.
#   2. `web` qui apparaît est vu SANS reload de nginx. Sans `resolver`, nginx fige
#      la résolution de `web` au démarrage et garde l'IP pour la vie du process.
#   3. `web` RECRÉÉ (nouvelle IP — c'est ce qu'est un deploy) est vu, toujours
#      sans reload. C'est la propriété qui manquait : chaque deploy laissait nginx
#      taper une IP morte jusqu'à ce que compose recrée nginx à son tour.
#
# Ne touche pas à la prod : tout se passe sur un réseau Docker jetable.
#
# Usage : nginx/test-resilience.sh
set -uo pipefail

NET=house-proxy-test-$$
NGINX=house-proxy-test-nginx-$$
WEB=house-proxy-test-web-$$
CURL=curlimages/curl:8.11.1
CONF="$(cd "$(dirname "$0")" && pwd)"
FAILURES=0

cleanup() {
  docker rm -f "$NGINX" "$WEB" "${WEB}-2" "${WEB}-fill" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
}
trap cleanup EXIT

fail() { echo "  ✗ $1"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $1"; }

# Les montages reproduisent ceux de docker-compose.prod.yml — répertoires, jamais
# fichiers seuls (voir l'étape 0b).
MOUNTS=(-v "$CONF/conf.d:/etc/nginx/conf.d:ro" -v "$CONF/html:/usr/share/nginx/html:ro")

run_nginx_t() {
  docker run --rm "${MOUNTS[@]}" nginx:alpine nginx -t
}

# curl depuis le réseau interne : nginx n'est pas exposé sur l'hôte.
fetch() { # fetch <path> -> corps + dernière ligne = code HTTP
  docker run --rm --network "$NET" "$CURL" \
    -s -w '\n%{http_code}' --max-time 10 "http://${NGINX}$1" 2>/dev/null || printf '\n000'
}
code() { fetch "$1" | tail -1; }
body() { fetch "$1" | sed '$d'; }

ip_of() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1"; }

# Attend, à travers nginx, que le corps devienne <attendu>. La bascule n'est PAS
# instantanée : nginx garde la résolution de `web` pendant le `valid=` du resolver.
# On chronomètre donc la convergence au lieu de la supposer immédiate — c'est cette
# borne qui est la propriété intéressante.
converges_in() { # converges_in <path> <attendu> <timeout_s> -> secondes écoulées, ou "" si jamais
  local waited=0
  while [ "$waited" -le "$3" ]; do
    [ "$(body "$1")" = "$2" ] && { echo "$waited"; return 0; }
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

# Attend que web réponde — interrogé EN DIRECT, pas à travers nginx : sinon un
# nginx à la résolution figée se lirait « web pas prêt ».
start_web() { # start_web <nom-conteneur> <marqueur>
  # `app.js` sert au contrôle de compression : `python -m http.server` l'annonce en
  # `text/javascript`, exactement comme Django. Il doit dépasser `gzip_min_length`.
  docker run -d --network "$NET" --network-alias web --name "$1" \
    python:3.12-slim \
    sh -c "mkdir -p /w && echo $2 > /w/probe.txt \
      && python -c \"open('/w/app.js','w').write('const x = 1;'.ljust(4096))\" \
      && cd /w && exec python -m http.server 8000" >/dev/null
  for _ in $(seq 1 30); do
    direct=$(docker run --rm --network "$NET" "$CURL" -s --max-time 5 http://web:8000/probe.txt 2>/dev/null)
    [ "$direct" = "$2" ] && return 0
    sleep 1
  done
  return 1
}

echo "→ 0. Syntaxe nginx"
if run_nginx_t >/dev/null 2>&1; then
  pass "nginx -t"
else
  fail "nginx -t rejette default.conf"
  run_nginx_t 2>&1 | sed 's/^/    /'
  exit 1
fi

# Ce script monte lui-même ce qu'il teste — donc il ne prouve RIEN sur ce que la
# prod monte. Deux deploys sont passés par ce trou : une page absente du conteneur
# (503 vide), puis un conf figé sur un inode mort. Le contrat compose se vérifie
# donc explicitement, ici, et pas par ressemblance.
echo "→ 0b. Les montages de la prod sont ceux que ce test suppose"
COMPOSE_FILE="$(dirname "$CONF")/docker-compose.prod.yml"

if grep -q '\./nginx/conf\.d:/etc/nginx/conf\.d' "$COMPOSE_FILE"; then
  pass "le conf est monté par répertoire"
else
  fail "compose ne monte pas ./nginx/conf.d — le conf ne suivrait pas un git reset"
fi

# La régression exacte : revenir à un bind mount de fichier unique. L'inode est
# épinglé au démarrage du conteneur, et git remplace le fichier au lieu de
# l'éditer — le conteneur garde donc l'ancien contenu pour toujours, `nginx -s
# reload` compris.
if grep -qE '\./nginx/(conf\.d/)?[a-z]+\.conf:' "$COMPOSE_FILE"; then
  fail "un fichier .conf est monté seul — l'inode sera épinglé, le conf figé"
else
  pass "aucun fichier .conf monté seul"
fi

if grep -q '\./nginx/html:/usr/share/nginx/html' "$COMPOSE_FILE"; then
  pass "la page de maintenance est montée"
else
  fail "compose ne monte pas nginx/html — la prod servirait un 503 vide"
fi

docker network create "$NET" >/dev/null
docker run -d --network "$NET" --name "$NGINX" "${MOUNTS[@]}" nginx:alpine >/dev/null
sleep 3

echo "→ 1. nginx sans upstream : page de maintenance, pas d'erreur technique"
if [ "$(docker inspect -f '{{.State.Running}}' "$NGINX" 2>/dev/null)" = "true" ]; then
  pass "nginx tourne alors que web est absent"
else
  fail "nginx s'est arrêté faute d'upstream"
  docker logs "$NGINX" 2>&1 | tail -10 | sed 's/^/    /'
  exit 1
fi

got=$(code /app/money)
[ "$got" = "503" ] && pass "GET /app/money → 503" || fail "GET /app/money → $got (attendu 503)"

page=$(body /app/money)
case "$page" in
  *"<hr><center>nginx</center>"*) fail "la page d'erreur nginx brute est servie" ;;
    # Motif volontairement **sans accent** : ce `case` compare des octets, et faire
    # dépendre un job bloquant pour le deploy de l'encodage d'un « é » n'apporte
    # rien. Ce test atteste qu'une page de maintenance est servie ; que celle-ci
    # dise « Maisonnée » est l'affaire de `apps/core/tests/test_product_name.py`.
    # Une assertion par test — et le nom du produit peut changer sans toucher ici.
    *"revient dans un instant"*)    pass "la page de maintenance est servie" ;;
  *)                              fail "corps inattendu : $(printf '%s' "$page" | head -c 120)" ;;
esac

got=$(code /api/households/)
[ "$got" = "503" ] && pass "GET /api/households/ → 503" || fail "GET /api/households/ → $got (attendu 503)"
api=$(body /api/households/)
case "$api" in
  *'"detail"'*) pass "l'API répond du JSON, pas du HTML" ;;
  *)            fail "l'API répond autre chose que du JSON : $(printf '%s' "$api" | head -c 120)" ;;
esac

echo "→ 2. web qui démarre est vu sans reload de nginx"
if start_web "$WEB" FIRST; then
  if waited=$(converges_in /probe.txt FIRST 20); then
    pass "web atteint sans reload (en ${waited}s)"
  else
    fail "web injoignable sans reload après 20s (corps : $(body /probe.txt | head -c 80))"
  fi
else
  fail "web n'a jamais répondu (problème de harnais, pas de nginx)"
fi

# Le bundle React partait brut parce que `gzip_types` ne connaissait que
# `application/javascript`, quand Django annonce les `.js` en `text/javascript` :
# 824 Ko au lieu de 257 Ko, et rien pour le signaler (issue #452). Le CSS, lui,
# passait — la compression avait donc l'air de marcher.
echo "→ 2b. un .js est bien compressé (le CSS ne suffit pas à le prouver)"
hdr=$(docker run --rm --network "$NET" "$CURL" -sD - -o /dev/null \
        -H 'Accept-Encoding: gzip' --max-time 10 "http://${NGINX}/app.js" 2>/dev/null \
        | tr -d '\r' | grep -iE '^content-(type|encoding):' | tr 'A-Z' 'a-z' | paste -sd' ' -)
case "$hdr" in
  *text/javascript*gzip*|*gzip*text/javascript*) pass "text/javascript → content-encoding: gzip" ;;
  *text/javascript*) fail "un .js en text/javascript sort NON compressé — gzip_types ?" ;;
  *)                 fail "app.js n'a pas été servi en text/javascript (reçu : ${hdr:-rien})" ;;
esac

echo "→ 3. web recréé (nouvelle IP, = un deploy) est vu sans reload"
old_ip=$(ip_of "$WEB")
docker rm -f "$WEB" >/dev/null 2>&1
# Occupe l'adresse libérée, sinon Docker la recycle et le test ne prouve rien.
docker run -d --network "$NET" --name "${WEB}-fill" alpine sleep 600 >/dev/null
if start_web "${WEB}-2" SECOND; then
  new_ip=$(ip_of "${WEB}-2")
  if [ "$old_ip" = "$new_ip" ]; then
    fail "harnais : IP recyclée ($new_ip), le test ne prouverait rien"
  elif waited=$(converges_in /probe.txt SECOND 20); then
    pass "nouvelle IP suivie sans reload en ${waited}s ($old_ip → $new_ip)"
  else
    fail "nginx tape encore l'ancienne IP $old_ip après 20s — resolver perdu ?"
  fi
else
  fail "le nouveau web n'a jamais répondu (problème de harnais, pas de nginx)"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "Tout est vert."
else
  echo "$FAILURES échec(s). Logs nginx :"
  docker logs "$NGINX" 2>&1 | tail -20 | sed 's/^/    /'
fi
exit "$FAILURES"
