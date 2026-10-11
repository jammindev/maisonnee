import { toLocalISODate } from '@/lib/format';

/**
 * Les deux fenêtres de la carte Eau du tableau de bord (#683).
 *
 * À part parce que c'est du calendrier, donc de l'espace déterministe : même
 * entrée, même sortie, et ça se vérifie sans rendu.
 *
 * **Pourquoi deux fenêtres et pas une.** Le chiffre de tête est un *débit*
 * moyen (L/jour) sur 30 jours glissants : robuste, toujours calculable, et
 * insensible au fait qu'un mois soit commencé. La sparkline, elle, est une
 * *tendance* : elle a besoin de mois entiers.
 */

/** Les 30 derniers jours, bornes incluses. */
export function last30Days(today: Date): { from: string; to: string } {
  const from = new Date(today);
  from.setDate(from.getDate() - 30);
  return { from: toLocalISODate(from), to: toLocalISODate(today) };
}

/**
 * Les `count` derniers mois **révolus** — le mois en cours est exclu.
 *
 * C'est tout l'objet du correctif de la sparkline : un mois entamé est
 * mécaniquement plus bas que les autres, donc l'inclure ferait plonger la courbe
 * à droite **tous les mois**, et une tendance qui descend toujours se lit
 * « on consomme de moins en moins ». Le chiffre de tête, lui, couvre le récent.
 */
export function lastCompleteMonths(today: Date, count: number): { from: string; to: string } {
  const year = today.getFullYear();
  const month = today.getMonth();
  // Jour 0 du mois courant = dernier jour du mois précédent.
  const end = new Date(year, month, 0);
  const start = new Date(year, month - count, 1);
  return { from: toLocalISODate(start), to: toLocalISODate(end) };
}
