<div align="center">

<img src="docs/assets/brand/logo-mark.svg" alt="" width="72" />

# Maisonnée

**Tout ce qu'un foyer fait vivre — et une mémoire capable d'en répondre.**
Dedans comme dehors : les chantiers, les comptes, les compteurs, le potager, les bêtes.

[**Voir la démo en ligne →**](https://demo.maisonnee.jammin-dev.com) ·
[Installer](#linstaller-en-trois-lignes) · [Ce que ça fait](#ce-que-ça-fait) ·
[Sans clé d'API](#sans-clé-dapi) ·
[Ce que ça ne fait pas](#ce-que-ça-ne-fait-pas) ·
[Doc auto-hébergement](docs/self-hosting/README.md) · [English](README.md)

</div>

![L'assistant répond sur le foyer en citant le carnet de rénovation et le chantier auquel il appartient](docs/assets/screenshots/01-assistant.png)

> *« On veut refaire le sol des WC dans le même carrelage que la salle de bain.
> C'était quoi la référence, et est-ce qu'il en reste ? »* — et la réponse arrive
> avec la marque, la référence, **où sont rangées les deux boîtes de rechange**,
> et un lien vers les deux fiches qu'elle a lues. Personne ne s'en souvient trois
> ans plus tard. La maison, si.
>
> *(L'interface des captures est en anglais — c'est la langue du README que lit
> un inconnu. Elle parle aussi français, allemand et espagnol.)*

---

## L'idée

Les logiciels de foyer vous font choisir un coin. Une appli de budget pour
l'argent. Une appli de tâches pour les corvées. Un tableur pour les relevés de
compteur. Une note quelque part pour la révision de la chaudière. Chacun fait
bien son travail, aucun ne connaît les autres — donc rien ne tombe jamais juste,
et rien ne peut être **demandé**.

Maisonnée tient **un seul registre pour tout le foyer**, et pose un assistant
dessus. L'ordre compte : l'assistant n'est pas un chatbot vissé sur une base de
données, c'est la raison pour laquelle tenir un registre unique en vaut la peine.

Tout ce que vous enregistrez est retrouvable et citable — près de deux douzaines
de natures : chantiers, entrées de journal, carnet de rénovation, documents *et
le texte qu'ils contiennent*, équipements, contrats, tâches, zones, relevés de
compteur, stock, poules, contacts. On pose une question en langage courant, et la
réponse revient **avec ses sources**, chacune étant un lien vers la fiche d'où
elle sort.

- *« Quel équipement est encore sous garantie ? »*
- *« La salle de bain a coûté combien, tout compris ? »*
- *« La chaudière a été révisée quand, et par qui ? »*
- *« C'est quelle peinture, sur le mur de la chambre de l'ado ? »*

L'assistant sait aussi **écrire** : créer une tâche ou une note depuis la
conversation, avec une annulation en un clic. Il tient une **mémoire** de ce
qu'on lui demande de retenir, et une conversation peut être **ancrée** à un
chantier ou à un équipement — il en connaît alors le contexte avant la première
question.

## L'installer en trois lignes

```bash
curl -O https://raw.githubusercontent.com/jammindev/maisonnee/main/docker-compose.yml
docker compose up -d
open http://localhost:8000
```

Pas de Python, pas de Node, pas de `git clone`, aucune clé à souscrire. Le
premier démarrage tire l'image, crée la base et applique le schéma. Le navigateur
demande ensuite le reste — votre e-mail, votre mot de passe, un nom pour votre
foyer. Rien à recopier depuis un terminal.

Tourne en `amd64` et `arm64` : un Raspberry Pi 4/5, un boîtier N100 ou un
Synology suffisent. Environ 2 Go de RAM et 5 Go de disque.

Guide complet : [docs/self-hosting/install.md](docs/self-hosting/install.md).

## Ce que ça fait

### La mémoire dans laquelle il puise

![Le journal du foyer : notes, entretiens et carnet de rénovation dans une même chronologie](docs/assets/screenshots/02-journal.png)

Un seul journal tient ce qu'un foyer a réellement besoin de retenir : des notes,
les entretiens faits sur un équipement, et un **carnet de rénovation** qui garde
la marque et la référence de ce qui a été posé, pièce par pièce. Les documents
sont indexés par leur contenu, pas seulement par leur nom de fichier : une
facture scannée se retrouve par ce qui est imprimé dessus.

C'est là-dedans que l'assistant lit. Et ça s'utilise très bien seul : chercher,
filtrer, suivre le lien d'un chantier vers les tickets qui l'ont payé.

### La journée, en un écran

![Le tableau de bord : ce qui demande attention, l'argent et le dehors côte à côte](docs/assets/screenshots/03-dashboard.png)

Ce qui demande attention, ce qui est dû cette semaine, et les constantes du
foyer — dépenses, eau, œufs — dans le même coup d'œil.

### L'argent, jusqu'à la ligne

![Le journal bancaire : chaque opération telle que la banque l'a écrite, chacune ventilée ou signalée](docs/assets/screenshots/04-bank-journal.png)

On importe un relevé CSV et on le rapproche. Une même ligne peut se ventiler
entre plusieurs budgets **et** se rattacher à un chantier : 150 € chez Leroy
Merlin, c'est 90 € de « la salle de bain » et 60 € d'entretien courant — et c'est
précisément ce qui rend « la salle de bain a coûté combien » répondable. Un
remboursement recrédite l'enveloppe. Un virement interne cesse de compter comme
une dépense. Un onglet **Contrôle** liste, avec un motif, tout ce que l'app ne
sait pas justifier.

La règle qui fonde ce versant : **chaque euro est soit rangé, soit signalé** —
rien ne reste dans un entre-deux silencieux.

![Les budgets : catégories imbriquées, plafonds, et ce qui dépasse](docs/assets/screenshots/05-budgets.png)

Le plafond est **facultatif** : « Cadeaux » peut être une catégorie suivie sans
limite, parce qu'inventer un montant pour obtenir une catégorie rend toutes les
autres barres illisibles.

### Le dehors n'est pas un module en plus

![Le poulailler : ponte, granulé, coût par œuf, corvées et troupeau](docs/assets/screenshots/06-chicken-coop.png)

Poules, eau, électricité, stock, potager — même registre que le reste, et c'est
pour ça que le poulailler sait dire ce que coûte un œuf.

![Le tableau électrique : rangées, disjoncteurs et différentiels, tels qu'ils sont dans la cave](docs/assets/screenshots/07-electricity.png)

Le tableau, dessiné tel qu'il est — ce qu'on veut avoir sous les yeux quand ça
disjoncte et qu'on est dans la cave avec une lampe torche.

Et les choses ordinaires : tâches et corvées récurrentes, zones et équipements,
contrats d'assurance, liste de courses, photos.

## Sans clé d'API

**Presque tout fonctionne quand même, et rien n'est amputé.** Chaque fiche que
l'assistant lit, vous pouvez la créer, la modifier, la chercher et la relier
**depuis l'interface** — l'app était un registre de foyer complet avant d'avoir
un assistant, et elle l'est restée.

Ce qu'une clé ajoute, et rien d'autre :

| Demande une clé | Ce que vous avez sans |
|---|---|
| L'assistant conversationnel | La recherche plein texte sur les mêmes fiches, avec surlignage |
| La recherche sémantique | La recherche par mots-clés, qui couvre l'essentiel |
| Le récap mensuel raconté | Le bilan mensuel, avec les mêmes chiffres |
| La lecture du texte d'un document scanné | Le document lui-même, et tout ce que vous en écrivez |

Les notifications push, l'e-mail et le bot Telegram suivent la même règle :
fournissez le service et ça s'allume, passez votre tour et le reste est intact.

**Et l'app le dit franchement.** Une capacité indisponible est annoncée là où on
s'en serait servi, avec la variable à poser et un lien vers le guide — jamais un
bouton qui échoue. Les clés se posent par instance, dans votre `.env` ; rien ne
part nulle part que vous n'ayez configuré. Voir
[docs/self-hosting/ai-providers.md](docs/self-hosting/ai-providers.md).

## Ce que ça ne fait pas

Écrit ici pour que vous le sachiez avant d'installer :

- **Pas d'agrégation bancaire.** Vous exportez un CSV et vous l'importez.
- **Pas de version hébergée.** Vous la faites tourner, ou pas.
- **Pas d'appli mobile native.** C'est une PWA : installable, consultable hors
  ligne, et elle reçoit les photos partagées depuis Android et iOS.
- **Pas de télémétrie.** Rien n'appelle la maison. Jamais.
- **Pas de multi-devise.** Les montants sont en euros.
- **Ce n'est pas un produit d'équipe.** Ça modélise un foyer : quelques personnes
  qui se font confiance et partagent un toit.

## État du projet

**v0.1.0.** Construit pour un foyer réel, utilisé quotidiennement par lui depuis
2025. Il n'a eu qu'un seul utilisateur pendant l'essentiel de sa vie, ce qui se
voit dans les deux sens : ce que ce foyer utilise est poli par l'usage, ce qu'il
n'utilise pas est plus jeune qu'il n'en a l'air.

- L'interface parle **anglais, français, allemand et espagnol**.
- La documentation interne et une partie des commentaires sont **en français** :
  choix assumé et documenté, voir [CONTRIBUTING.md](CONTRIBUTING.md).
- La sauvegarde **et la restauration** sont scriptées et rejouées en CI à chaque
  release, parce qu'une sauvegarde que personne n'a restaurée n'est pas une
  sauvegarde.
- Une migration destructive se livre en deux fois : une mise à jour ne demande
  jamais que vous soyez devant l'écran.

Si vous l'installez, la chose la plus utile que vous puissiez faire est de dire à
l'auteur ce qui a cassé. Ça vaut plus, en ce moment, qu'une pull request.

## Documentation

| | |
|---|---|
| [Auto-hébergement](docs/self-hosting/README.md) | Installation, sauvegarde et restauration, mises à jour, dépannage |
| [Fournisseurs d'IA](docs/self-hosting/ai-providers.md) | Quelle clé débloque quoi, et ce qui se passe sans |
| [Contribuer](CONTRIBUTING.md) | Comment aider, et dans quelle langue le projet est écrit |
| [Sécurité](SECURITY.md) | Signaler une faille, en privé |
| [Hub de la doc](docs/README.md) | Parcours, fiches concept, modules |

## Licence

[AGPL-3.0-only](LICENSE). Faites-la tourner, modifiez-la, partagez-la. Si vous
hébergez une version modifiée *pour d'autres*, publiez vos modifications —
l'héberger pour votre propre famille n'est pas « pour d'autres », c'est l'usage
normal de ce logiciel.

Le **nom et le signe ne sont pas couverts par la licence** ; un fork redistribué
porte son propre nom. Les détails :
[docs/assets/brand/README.md](docs/assets/brand/README.md).
