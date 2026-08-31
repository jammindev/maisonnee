"""Les garde-fous de l'identité — vérifiés depuis Python, seul côté qui voit tout.

Trois défauts possibles, tous silencieux, tous rencontrés en écrivant le lot 8 :

1. **Un SVG invalide ne s'affiche pas, et ne dit rien.** Le premier
   `logo-mark.svg` contenait « ``--primary`` » dans son commentaire d'en-tête, or
   XML interdit ``--`` dans un commentaire. Le fichier était donc du XML cassé :
   ``<img>`` refusait de le charger, le logo était absent *partout*, et la seule
   trace était un `Event` sans message dans `onerror`. Rien n'aurait rougi.

2. **Le tracé recopié dérive de sa source.** `ui/src/design-system/logo.tsx`
   recopie le ``d`` de `logo-mark.svg` plutôt que de l'importer (un `import` de
   SVG dépendrait d'un plugin de bundler, et `docs/` est hors du root Vite). Deux
   exemplaires d'une même valeur divergent toujours — sauf si quelque chose les
   compare.

3. **Une icône référencée et absente** produit un carré vide sur l'écran
   d'accueil d'un téléphone, et personne ne teste l'installation d'une PWA.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import xml.dom.minidom
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BRAND = REPO / "docs" / "assets" / "brand"
ICONS = REPO / "static" / "icons"
LOGO_TSX = REPO / "ui" / "src" / "design-system" / "logo.tsx"
MANIFEST = REPO / "templates" / "manifest.json"
INDEX = REPO / "templates" / "index.html"

BRAND_COLOR = "#3F5741"

REPOSITORY_SLUG = "jammindev/maisonnee"
FORMER_REPOSITORY_SLUG = "jammindev/house"

# Les seuls fichiers autorisés à porter l'ancien slug : il y est un **fait daté**
# (« public depuis le 21 septembre 2025 »), pas un lien vivant. Réécrire l'histoire
# coûte plus que de l'assumer — même règle que « les anciennes issues ne se
# traduisent pas ». Ce fichier de test s'y ajoute : il doit bien nommer ce qu'il
# refuse.
FILES_WHERE_THE_FORMER_NAME_IS_HISTORY = {
    "docs/parcours/PARCOURS_28_OUVRIR_MAISONNEE.md",
    "docs/parcours/PARCOURS_28_BACKLOG_TECHNIQUE.md",
    "docs/journal/2026-07-31_parcours-28_cadrage_initial.md",
    "apps/core/tests/test_brand_assets.py",
}

# Les endroits qui recopient le slug hors des workflows. Chacun est un deuxième
# exemplaire d'une même valeur — donc quelque chose doit les comparer.
FILES_QUOTING_THE_SLUG = (
    "ui/src/lib/api/changelog.ts",
    "ui/src/features/settings/components/AboutSection.tsx",
    "apps/app_settings/capabilities.py",
    "README.md",
    "README.fr.md",
    "docker-compose.yml",
)


def _svg_files():
    return sorted(BRAND.glob("*.svg")) + sorted(ICONS.glob("*.svg"))


class TestEverySvgIsWellFormed:
    """Un SVG cassé se comporte comme un SVG absent, sans le dire."""

    def test_the_discovery_finds_the_brand_files(self):
        # Sans ce garde-fou, un dossier renommé rendrait la classe entière verte
        # en ne validant rien.
        found = {p.name for p in _svg_files()}
        assert {"logo-mark.svg", "logo.svg", "logo-wordmark.svg"} <= found, found

    @pytest.mark.parametrize("path", _svg_files(), ids=lambda p: p.name)
    def test_it_parses_as_xml(self, path):
        try:
            xml.dom.minidom.parse(str(path))
        except Exception as exc:  # noqa: BLE001 — on veut le message brut
            pytest.fail(f"{path.relative_to(REPO)} n'est pas du XML valide : {exc}")

    @pytest.mark.parametrize("path", _svg_files(), ids=lambda p: p.name)
    def test_no_double_hyphen_in_comments(self, path):
        """Le piège exact du premier jet, nommé pour qu'il ne revienne pas."""
        for comment in re.findall(r"<!--(.*?)-->", path.read_text(), flags=re.S):
            assert "--" not in comment, (
                f"{path.relative_to(REPO)} : « -- » dans un commentaire XML, "
                "ce qui rend le fichier invalide et le logo invisible."
            )


class TestTheMarkHasASingleDefinition:
    """Le tracé du composant et celui de la source de marque ne divergent pas."""

    def test_the_path_matches_the_brand_source(self):
        svg = (BRAND / "logo-mark.svg").read_text()
        tsx = LOGO_TSX.read_text()

        in_svg = re.search(r'\sd="([^"]+)"', svg)
        assert in_svg, "aucun attribut d= dans logo-mark.svg"
        in_tsx = re.search(r"LOGO_MARK_PATH\s*=\s*\n?\s*'([^']+)'", tsx)
        assert in_tsx, "LOGO_MARK_PATH introuvable dans logo.tsx"

        normalise = lambda d: re.sub(r"\s+", " ", d).strip()  # noqa: E731
        assert normalise(in_tsx.group(1)) == normalise(in_svg.group(1)), (
            "Le tracé de logo.tsx a dérivé de docs/assets/brand/logo-mark.svg. "
            "La source est le SVG."
        )

    def test_the_component_carries_no_colour_of_its_own(self):
        """La marque est en `currentColor`, jamais dans une couleur de thème."""
        code = "\n".join(
            line
            for line in LOGO_TSX.read_text().splitlines()
            if not line.lstrip().startswith(("*", "//", "/*"))
        )
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", code), "couleur en dur dans logo.tsx"
        assert not re.search(r"\b(?:rgb|hsl)a?\(", code), "couleur en dur dans logo.tsx"
        assert not re.search(r"(?:bg|text|fill|stroke)-primary", code), (
            "la marque reprend `--primary`, que les 17 thèmes repeignent"
        )


class TestThePwaIconsExistAndAreDistinct:
    """`any` et `maskable` sont deux fichiers, pas un `purpose` à deux mots."""

    def test_every_manifest_icon_exists_on_disk(self):
        manifest = json.loads(MANIFEST.read_text())
        for icon in manifest["icons"]:
            path = REPO / icon["src"].lstrip("/")
            assert path.is_file(), f"{icon['src']} est référencé et absent"

    def test_any_and_maskable_are_different_files(self):
        """Android rogne 20 % de chaque bord d'une icône `maskable`.

        Avant ce lot, les deux `purpose` pointaient le **même** PNG, avec
        `"purpose": "any maskable"` : Android rognait donc dans le dessin. Le
        manifeste était parfaitement valide, et l'icône installée amputée.
        """
        manifest = json.loads(MANIFEST.read_text())
        by_purpose: dict[str, set[str]] = {}
        for icon in manifest["icons"]:
            for purpose in icon.get("purpose", "any").split():
                by_purpose.setdefault(purpose, set()).add(icon["src"])

        assert "maskable" in by_purpose, "aucune icône maskable déclarée"
        assert "any" in by_purpose, "aucune icône `any` déclarée"
        shared = by_purpose["any"] & by_purpose["maskable"]
        assert not shared, (
            f"Ces fichiers servent aux deux usages : {sorted(shared)}. "
            "Une icône maskable doit garder le signe dans les 80 % centraux ; "
            "servir l'icône `any` la fait rogner dans le dessin."
        )

    def test_the_manifest_wears_the_product_name(self):
        manifest = json.loads(MANIFEST.read_text())
        assert manifest["name"] == "Maisonnée"
        assert manifest["short_name"] == "Maisonnée"
        # Le gris `#f3f4f6` d'avant n'était la marque de personne.
        assert manifest["theme_color"].upper() == BRAND_COLOR
        assert manifest["background_color"].upper() == BRAND_COLOR

    def test_the_page_links_icons_that_exist(self):
        html = INDEX.read_text()
        for href in re.findall(r'<link[^>]+href="(/static/icons/[^"]+)"', html):
            assert (REPO / href.lstrip("/")).is_file(), f"{href} est lié et absent"
        assert "<title>Maisonnée</title>" in html


class TestTheFrontDoorHasNoDeadLinks:
    """Les deux README sont la seule page que 95 % des visiteurs verront.

    Un lien mort y coûte plus cher que partout ailleurs : c'est la première
    chose qu'un inconnu clique, et il n'a aucune raison de supposer que le reste
    du dépôt est plus soigné. Renommer une capture ou déplacer un doc casse le
    README sans qu'aucun test existant ne s'en aperçoive — le fichier reste
    parfaitement valide, il pointe simplement dans le vide.
    """

    READMES = ("README.md", "README.fr.md")

    @pytest.mark.parametrize("readme", READMES)
    def test_every_relative_link_resolves(self, readme):
        text = (REPO / readme).read_text()
        dead = []
        for target in re.findall(r"\]\(([^)]+)\)", text):
            target = target.split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (REPO / target).exists():
                dead.append(target)
        assert not dead, f"{readme} pointe dans le vide : {sorted(set(dead))}"

    @pytest.mark.parametrize("readme", READMES)
    def test_every_image_resolves(self, readme):
        text = (REPO / readme).read_text()
        dead = [
            src
            for src in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
            if not src.startswith("http") and not (REPO / src.split("#")[0]).exists()
        ]
        # Les balises <img> du bandeau centré comptent aussi.
        dead += [
            src
            for src in re.findall(r'<img[^>]+src="([^"]+)"', text)
            if not src.startswith("http") and not (REPO / src).exists()
        ]
        assert not dead, f"{readme} affiche des images absentes : {sorted(set(dead))}"

    def test_the_social_preview_says_what_the_readme_says(self):
        """L'aperçu social et le README portent la **même** promesse.

        Ce sont deux exemplaires d'un même texte, et deux exemplaires d'une
        valeur divergent toujours — c'est la raison d'être de
        `TestTheMarkHasASingleDefinition` juste au-dessus, appliquée à de la
        prose. Ça s'est produit dans la journée : le README a été recadré sur
        l'assistant (« *and a memory that can answer for it* », l'argent
        redescendu dans la liste), l'image est restée sur la version d'avant.
        Rien n'a rougi, et c'est l'image — pas le README — que voit en premier
        quelqu'un à qui on partage le lien.

        La comparaison se fait sur la **source du harnais**, jamais sur le PNG :
        un pixel ne dit pas ce qu'il raconte. Et sur le README anglais seul,
        parce que c'est celui que GitHub sert par défaut et que la carte est en
        anglais.
        """
        html = (REPO / "scripts/brand/social-preview.html").read_text()

        def spoken(css_class: str) -> str:
            block = re.search(rf'class="{css_class}">(.*?)</div>', html, flags=re.S)
            assert block, f"aucun bloc .{css_class} dans le harnais"
            text = re.sub(r"<br\s*/?>", " ", block.group(1))
            text = text.replace("&mdash;", "—").replace("&eacute;", "é")
            return re.sub(r"\s+", " ", text).strip()

        readme = (REPO / "README.md").read_text()
        tagline = re.search(r"^\*\*(.+?)\*\*$", readme, flags=re.M)
        assert tagline, "aucune accroche en gras dans README.md"
        subtitle = readme.split(tagline.group(0), 1)[1].splitlines()[1].strip()

        assert spoken("lede") == tagline.group(1).strip(), (
            "L'accroche de l'aperçu social a dérivé de celle du README.\n"
            f"  README : {tagline.group(1).strip()}\n"
            f"  image  : {spoken('lede')}\n"
            "Corriger scripts/brand/social-preview.html, puis "
            "`npm run brand:social`."
        )
        assert spoken("sub") == subtitle, (
            "Le sous-titre de l'aperçu social a dérivé de celui du README.\n"
            f"  README : {subtitle}\n"
            f"  image  : {spoken('sub')}"
        )

    def test_the_social_preview_is_the_size_github_expects(self):
        """1280×640. Lu dans l'en-tête PNG, sans dépendance d'image.

        Une carte au mauvais ratio n'échoue pas : GitHub la recadre, et le
        rognage tombe où il veut — en pratique sur la moitié de l'accroche.
        """
        import struct

        header = (BRAND / "social-preview.png").read_bytes()[:24]
        assert header[:8] == b"\x89PNG\r\n\x1a\n", "ce n'est pas un PNG"
        width, height = struct.unpack(">II", header[16:24])
        assert (width, height) == (1280, 640), f"aperçu social en {width}×{height}"

    def test_the_screenshots_are_the_six_the_harness_produces(self):
        """Les captures versionnées sont celles que `npm run screenshots` écrit.

        Sans ce contrôle, une capture ajoutée à la main — donc venue d'un vrai
        foyer — passerait inaperçue. C'est le critère 3 du lot 6 : aucune donnée
        d'un foyer réel dans `docs/assets/`.
        """
        spec = (REPO / "scripts/screenshots/capture.spec.ts").read_text()
        declared = set(re.findall(r"name: '([^']+)'", spec))
        on_disk = {p.stem for p in (REPO / "docs/assets/screenshots").glob("*.png")}
        assert declared == on_disk, (
            f"déclarées par le harnais : {sorted(declared)} ; "
            f"présentes sur disque : {sorted(on_disk)}"
        )


class TestTheRepositoryHasASingleName:
    """Le dépôt s'appelle `maisonnee` — et rien ne doit dire l'inverse.

    Le renommage de `jammindev/house` en `jammindev/maisonnee` (2026-08-18) a mis
    au jour un défaut d'une famille bien connue ici : **un littéral qui devient
    faux sans rien casser.** Trois workflows gardaient leur job par
    ``if: github.repository == 'jammindev/house'``. Une fois le dépôt renommé, la
    condition ne lève pas — elle vaut `false`, le job est **sauté**, et la CI
    reste **verte**. Le job en question était `deploy` : un push sur `main` aurait
    cessé de déployer sans qu'aucun signal ne l'annonce.

    C'est le même défaut que le `onSuccess` qui oublie une racine de cache et que
    le `msgstr` vide : **en revue, le diff fautif ressemble exactement au diff
    juste.** Donc ça ne se relit pas, ça se teste.
    """

    def _tracked_text_files(self):
        listing = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for relative in filter(None, listing.split("\0")):
            try:
                yield relative, (REPO / relative).read_text()
            except (UnicodeDecodeError, OSError):
                continue  # binaire (images de marque) ou entrée sans fichier

    def test_the_declared_name_is_the_one_github_reports(self):
        """Le maillon qui ferme la boucle : le littéral face au dépôt réel.

        Les autres contrôles de cette classe comparent les exemplaires **entre
        eux** — ils attrapent une dérive interne, pas un dépôt renommé sous les
        pieds du code. Celui-ci lit `GITHUB_REPOSITORY`, que le runner pose, et
        c'est le seul qui aurait rougi à la seconde du renommage.

        Sur un fork il **skippe** : le slug amont ne s'applique pas à quelqu'un
        d'autre, et un contributeur qui découvre le projet ne doit pas hériter
        d'une CI rouge pour avoir cliqué sur « Fork ».

        En revanche il **refuse de skipper sur un runner GitHub**. Un contrôle
        qui se désactive tout seul est précisément le défaut que cette classe
        existe pour empêcher : la CI tourne en `-q`, qui n'imprime pas les
        raisons de skip, donc un `GITHUB_REPOSITORY` disparu (un `env:` posé sur
        l'étape, un autre exécuteur) rendrait ce test muet sans rien afficher.
        Le seul contrôle qui voit le dépôt réel ne doit pas pouvoir s'éteindre en
        silence.
        """
        actual = os.environ.get("GITHUB_REPOSITORY")
        # Les deux valeurs sont extraites dans des variables locales *avant* tout
        # `assert`. Une assertion portant sur `os.environ` fait introspecter la
        # table entière par pytest, qui l'imprime dans le rapport d'échec : sur ce
        # dépôt public, un rouge en CI publierait tout le contexte du runner dans
        # un log lisible par n'importe qui. Un test ne doit pas devenir une fuite
        # le jour où il rougit.
        on_a_github_runner = bool(os.environ.get("GITHUB_ACTIONS"))
        if not actual:
            assert not on_a_github_runner, (
                "sur un runner GitHub sans `GITHUB_REPOSITORY` : ce test est le "
                "seul à comparer le slug déclaré au dépôt réel, il ne doit pas "
                "se laisser désactiver par une variable manquante"
            )
            pytest.skip("hors runner GitHub : aucun nom de dépôt à comparer")
        owner, _, _name = actual.partition("/")
        if owner != REPOSITORY_SLUG.partition("/")[0]:
            pytest.skip(f"fork ({actual}) : le slug amont ne s'y applique pas")
        assert actual == REPOSITORY_SLUG, (
            f"GitHub annonce `{actual}` mais le code déclare "
            f"`{REPOSITORY_SLUG}` — tout `github.repository ==` du dépôt est donc "
            "faux, et les jobs qu'il garde (dont `deploy`) sont sautés en silence"
        )

    def test_the_discovery_sees_the_repository(self):
        """Un balayage qui ne trouve rien passerait pour un balayage propre."""
        found = dict(self._tracked_text_files())
        assert len(found) > 100, f"git ls-files n'a rendu que {len(found)} fichiers"
        assert "README.md" in found

    def test_no_living_file_names_the_former_repository(self):
        """L'ancien slug ne survit que là où il est un fait daté.

        Ailleurs il redirige *aujourd'hui* — GitHub garde la redirection tant que
        personne ne reprend le nom — et casse le jour où quelqu'un le reprend. Une
        promesse d'adresse qui dépend de la bienveillance d'un tiers n'est pas une
        adresse.
        """
        offenders = sorted(
            relative
            for relative, text in self._tracked_text_files()
            if FORMER_REPOSITORY_SLUG in text
            and relative not in FILES_WHERE_THE_FORMER_NAME_IS_HISTORY
        )
        assert not offenders, (
            "ces fichiers nomment encore l'ancien dépôt "
            f"`{FORMER_REPOSITORY_SLUG}` : {offenders}"
        )

    def test_every_workflow_gate_names_this_repository(self):
        """Chaque `github.repository == '…'` désigne bien ce dépôt.

        C'est le contrôle qui compte : ces égalités **gardent des jobs**, dont le
        deploy. Une valeur périmée ne rougit pas, elle éteint.
        """
        gates: dict[str, list[str]] = {}
        for workflow in sorted((REPO / ".github" / "workflows").glob("*.yml")):
            named = re.findall(
                r"github\.repository\s*==\s*'([^']+)'", workflow.read_text()
            )
            if named:
                gates[workflow.name] = named

        assert gates, (
            "aucun `github.repository ==` trouvé : soit les gardes ont disparu "
            "(alors ces workflows tournent aussi sur les forks), soit la syntaxe "
            "a changé et ce test ne voit plus rien"
        )
        wrong = {
            name: slugs
            for name, slugs in gates.items()
            if any(slug != REPOSITORY_SLUG for slug in slugs)
        }
        assert not wrong, (
            f"ces gardes visent un autre dépôt que `{REPOSITORY_SLUG}` — le job "
            f"gardé est silencieusement sauté : {wrong}"
        )

    @pytest.mark.parametrize("relative", FILES_QUOTING_THE_SLUG)
    def test_every_copy_of_the_slug_agrees(self, relative):
        """Un exemplaire de plus est un exemplaire qui peut dériver.

        `REPO_URL` du changelog, le lien « À propos », la base des liens de
        documentation des capacités, et la ligne `curl` que le lecteur du README
        tape en premier. Première question du filtre du dépôt : *est-ce que ça
        crée une deuxième définition ?* Oui — donc quelque chose doit les
        comparer.
        """
        text = (REPO / relative).read_text()
        assert REPOSITORY_SLUG in text, (
            f"{relative} ne nomme pas `{REPOSITORY_SLUG}` — la valeur a dérivé ou "
            "le fichier a changé de forme"
        )
