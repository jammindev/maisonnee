"""Un test qui rougit ne doit pas publier l'environnement dans lequel il tournait.

Constaté en écrivant le garde-fou de nom de dépôt : une assertion portant
directement sur ``os.environ.get("…")`` fait introspecter la table **entière** par
pytest, qui l'imprime dans le rapport d'échec. La sortie contenait un
``GITLAB_PRIVATE_TOKEN`` exporté depuis ``~/.zshrc`` — un jeton étranger au projet,
hérité par tout processus lancé depuis le shell.

Sur un dépôt **public**, ce rapport part dans un log GitHub Actions lisible par
n'importe qui, et rien ne surveillait ce chemin : ``gitleaks`` scanne les commits,
pas la sortie des tests.

Le filet vit dans ``conftest.py``. Ce fichier vérifie qu'il **caviarde vraiment**,
en faisant échouer de vrais tests dans un pytest imbriqué (``pytester``) et en
lisant la sortie produite. Un caviardeur qu'on n'a jamais vu caviarder ne protège
rien — c'est la même exigence que « une sauvegarde jamais restaurée n'est pas une
sauvegarde ».
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

# ⚠️ Les appâts sont **assemblés à l'exécution**, jamais écrits en un seul
# littéral. Un test qui vérifie qu'on caviarde les jetons GitLab a besoin de
# quelque chose qui a la forme d'un jeton GitLab — et `gitleaks`, qui tourne en CI
# sur chaque PR, le trouve et bloque : trois findings `gitlab-pat` la première
# fois. Ne pas « simplifier » en recollant les morceaux, et ne pas ajouter
# d'exception à gitleaks non plus : une exception se périme et finit par couvrir
# un vrai secret, alors qu'un littéral absent ne peut pas être trouvé.
_SHAPE = "gl" + "pat-"

# Deux appâts distincts : celui-ci vit dans l'environnement du run imbriqué…
CANARY = _SHAPE + "CanaryValueThatMustNeverBePrinted01"
# …et celui-là n'y est pas, pour éprouver la seconde jambe du filet.
CANARY_FROM_DISK = _SHAPE + "AnotherOneEntirelyFromDisk0123456"

# `pytester` lance un pytest imbriqué dans un répertoire vide : il faut lui
# redonner le conftest racine, qui porte le filet.
#
# Le chargement passe par `importlib` sous un nom explicite, et **pas** par un
# `from conftest import …` : le fichier généré ci-dessous s'appelle lui aussi
# `conftest.py` et pytest l'a déjà importé sous le nom `conftest`, donc l'import
# nominal se résoudrait sur lui-même et ne trouverait rien. Le pytest imbriqué
# mourait alors au démarrage, sans le moindre résumé — un échec qui ressemble à
# « aucun test collecté ».
CONFTEST_UNDER_TEST = '''
import importlib.util

_spec = importlib.util.spec_from_file_location("house_root_conftest", {root!r})
_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root)

_redact = _root._redact
pytest_runtest_makereport = _root.pytest_runtest_makereport
pytest_make_collect_report = _root.pytest_make_collect_report
'''

# `-p no:django` est indispensable : le sous-processus hérite le
# `DJANGO_SETTINGS_MODULE` du run parent, et `pytest-django` cherche alors le
# projet depuis le répertoire temporaire de `pytester`. Il n'y trouve pas
# `config`, lève un `ImportError` **avant** la collecte, et le run imbriqué
# n'imprime aucun résumé — ce qui se lit exactement comme « aucun test ».
NESTED_ARGS = ("-q", "-p", "no:django", "-p", "no:cacheprovider")


@pytest.fixture
def leaky(pytester, monkeypatch):
    """Un pytest imbriqué qui porte le filet et un secret dans l'environnement."""
    root_conftest = Path(__file__).resolve().parents[3] / "conftest.py"
    pytester.makeconftest(CONFTEST_UNDER_TEST.format(root=str(root_conftest)))
    monkeypatch.setenv("SOME_PRIVATE_TOKEN", CANARY)
    return pytester


class TestASecretNeverReachesTheReport:
    def test_the_canary_would_leak_without_the_net(self, leaky):
        """D'abord la preuve que le danger est réel, pas théorique.

        Sans cette étape, les tests suivants pourraient passer parce que pytest
        n'imprime rien du tout — on validerait un filet devant une fenêtre
        fermée. Ici on vérifie que l'introspection **atteint** bien la valeur :
        le nom de la variable, lui, n'est pas un secret et doit rester lisible.
        """
        leaky.makepyfile(
            """
            import os

            def test_boom():
                assert not os.environ.get("SOME_PRIVATE_TOKEN")
            """
        )
        result = leaky.runpytest_subprocess(*NESTED_ARGS)
        result.assert_outcomes(failed=1)
        assert "SOME_PRIVATE_TOKEN" in str(result.stdout), (
            "pytest n'a pas introspecté l'environnement : ce test ne prouve plus "
            "rien, il faut trouver un cas qui fuit réellement"
        )

    def test_the_environment_dump_is_redacted(self, leaky):
        """Le cas exact rencontré : un `assert` sur `os.environ.get(...)`."""
        leaky.makepyfile(
            """
            import os

            def test_boom():
                assert not os.environ.get("SOME_PRIVATE_TOKEN")
            """
        )
        result = leaky.runpytest_subprocess(*NESTED_ARGS)
        result.assert_outcomes(failed=1)
        assert CANARY not in str(result.stdout), (
            "la valeur du jeton est sortie dans le rapport d'échec"
        )
        assert "caviardé" in str(result.stdout)

    def test_a_secret_shape_is_redacted_even_outside_the_environment(self, leaky):
        """Un jeton lu dans un fichier n'est pas dans `os.environ`.

        Le filet a donc deux jambes : les valeurs de l'environnement, et les
        formes de jetons connues. Sans la seconde, un secret venu d'une fixture
        ou d'un `.env` de test passerait.
        """
        leaky.makepyfile(
            "def test_boom():\n"
            f"    lu_dans_un_fichier = {CANARY_FROM_DISK!r}\n"
            '    assert lu_dans_un_fichier == "attendu"\n'
        )
        result = leaky.runpytest_subprocess(*NESTED_ARGS)
        result.assert_outcomes(failed=1)
        assert CANARY_FROM_DISK not in str(result.stdout)

    def test_an_ordinary_failure_keeps_its_full_report(self, leaky):
        """Le filet ne doit pas dégrader ce qu'il n'a pas à protéger.

        Caviarder remplace un `longrepr` riche par du texte brut — plus de
        surlignage de la ligne fautive. C'est un bon échange sur un rapport qui
        fuit, et un mauvais sur tous les autres : un échec ordinaire garde donc
        son rapport intact, valeurs comparées incluses.
        """
        leaky.makepyfile(
            """
            def test_boom():
                attendu = 41
                assert attendu == 42
            """
        )
        result = leaky.runpytest_subprocess(*NESTED_ARGS)
        result.assert_outcomes(failed=1)
        out = str(result.stdout)
        assert "caviardé" not in out, "un échec sans secret a été dégradé pour rien"
        assert "41" in out and "42" in out, "le rapport a perdu les valeurs comparées"


class TestTheRedactorItself:
    """Les cas limites, testés sans passer par un pytest imbriqué."""

    def test_it_leaves_short_values_alone(self, monkeypatch):
        """`DEBUG_TOKEN=1` n'est pas un secret, et le caviarder ferait du bruit."""
        from conftest import _redact

        monkeypatch.setenv("SHORT_TOKEN", "1")
        cleaned, touched = _redact("la valeur est 1 dans ce texte")
        assert not touched
        assert cleaned == "la valeur est 1 dans ce texte"

    def test_it_ignores_names_that_are_not_secrets(self, monkeypatch):
        from conftest import _redact

        monkeypatch.setenv("HOSTNAME", "une-machine-au-nom-assez-long")
        cleaned, touched = _redact("tourne sur une-machine-au-nom-assez-long")
        assert not touched

    def test_it_redacts_the_longest_value_first(self, monkeypatch):
        """Deux secrets dont l'un est préfixe de l'autre.

        Caviarder le court d'abord laisserait la queue du long en clair.
        """
        from conftest import _redact

        monkeypatch.setenv("A_TOKEN", "secret-partie-un")
        monkeypatch.setenv("B_TOKEN", "secret-partie-un-et-deux")
        cleaned, touched = _redact("valeur=secret-partie-un-et-deux")
        assert touched
        assert "secret-partie-un" not in cleaned
        assert "et-deux" not in cleaned
