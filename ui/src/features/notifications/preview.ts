import type { NotificationItem } from '@/lib/api/notifications';

/**
 * Les lignes que la cloche montre, et dans quel ordre.
 *
 * **Le badge et l'aperçu ne peuvent pas avoir deux définitions.** Le badge
 * compte tous les non-lus (`unread-count`, côté serveur) ; l'aperçu était un
 * simple `slice` de la liste triée par date, donc l'état lu/non-lu n'entrait
 * pas dans le choix des lignes affichées. Cinq notifications lues arrivées
 * après un non-lu suffisaient à rendre ce non-lu **introuvable** dans la
 * cloche pendant que le badge affichait « 1 » : on l'ouvre pour trouver ce que
 * le badge annonce, et on ne le trouve pas.
 *
 * Le correctif n'est pas de retirer les lues. **Lire n'est pas supprimer** — le
 * modèle a déjà `deleted_at` pour écarter, et écarter est un geste explicite
 * (même règle que les arbitrages de conformité). Vider l'aperçu à la lecture
 * ferait disparaître la ligne sous le curseur au moment même où on la clique, et
 * personne ne pourrait revenir sur ce qu'il vient d'ouvrir. Les lues restent
 * donc là, elles cessent seulement de passer devant un non-lu.
 *
 * @param notifications la liste servie par l'API, déjà en `-created_at`
 * @param limit         la borne de l'aperçu
 * @param pinnedIds     l'ordre déjà affiché, à ne pas bousculer (voir plus bas)
 */
export function buildBellPreview(
  notifications: readonly NotificationItem[],
  limit: number,
  pinnedIds: readonly string[] = [],
): NotificationItem[] {
  const byId = new Map(notifications.map((n) => [n.id, n]));
  const taken = new Set<string>();
  const preview: NotificationItem[] = [];

  // Ce qui est déjà à l'écran garde sa place — mais on relit l'état frais de
  // chaque ligne : c'est l'**ordre** qui est figé, pas le contenu. Sans ce gel,
  // cliquer un non-lu le fait passer derrière les autres non-lus, la ligne
  // suivante monte sous le curseur et le second clic tombe à côté. Même règle
  // que la jambe sémantique de la recherche globale : on ajoute au bas de ce que
  // l'utilisateur lit, on ne réordonne jamais sous ses yeux.
  for (const id of pinnedIds) {
    const notification = byId.get(id);
    if (!notification || taken.has(id)) continue;
    preview.push(notification);
    taken.add(id);
  }

  // Puis les non-lues, puis les lues — chaque groupe gardant l'ordre
  // chronologique dans lequel l'API les a servies.
  const ranked = [
    ...notifications.filter((n) => !n.is_read),
    ...notifications.filter((n) => n.is_read),
  ];

  for (const notification of ranked) {
    if (preview.length >= limit) break;
    if (taken.has(notification.id)) continue;
    preview.push(notification);
    taken.add(notification.id);
  }

  return preview.slice(0, limit);
}
