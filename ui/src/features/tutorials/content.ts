import {
  AlertCircle, Landmark, LayoutDashboard, Newspaper, PartyPopper, PiggyBank, Receipt,
  ShieldCheck, Smartphone, Sparkles, User,
  type LucideIcon,
} from 'lucide-react';
import { MODULES } from '@/lib/modules';

/**
 * Registre du contenu des tutoriels — la SEULE source de vérité côté code.
 *
 * Toute la prose vit dans les fichiers de traduction (namespace `tutorials`) :
 * - guide     → `tutorials.guide.<key>.title` / `.intro`
 *               `tutorials.guide.<key>.steps.<stepId>.title` / `.body`
 * - checklist → `tutorials.start.items.<key>.title` / `.description`
 *
 * Maintenance (voir skill `/tutorials`) : ajouter une feature = une entrée ici
 * (ou un stepId dans un guide existant) + les clés dans les 4 locales. Aucun
 * backend à toucher : la progression est stockée comme liste de clés opaques
 * sur `User.completed_tutorials`.
 *
 * Les guides adossés à un module (`moduleKey`) sont masqués quand le module est
 * désactivé pour le foyer, et héritent de son icône **à défaut** d'une icône
 * explicite (nécessaire depuis que trois guides partagent le module « Argent »).
 */

export interface TutorialGuide {
  /** Clé stable — i18n `tutorials.guide.<key>.*` + progression `guide.<key>`. */
  key: string;
  /** Module du registre MODULES : masquage si désactivé, icône par défaut. */
  moduleKey?: string;
  /** Icône explicite — gagne sur celle du module. */
  Icon?: LucideIcon;
  /** Deep-link vers la page concernée par le guide. */
  to: string;
  /** Ids sémantiques des étapes — stables même si on insère/réordonne. */
  stepIds: string[];
}

export interface GettingStartedItem {
  /** Clé stable — i18n `tutorials.start.items.<key>.*` + progression `start.<key>`. */
  key: string;
  /** Deep-link vers la page où réaliser l'action. */
  to: string;
  /** Masque l'item si ce module est désactivé pour le foyer. */
  moduleKey?: string;
}

/** Checklist « Bien démarrer » — les premières actions clés dans l'app. */
export const GETTING_STARTED: GettingStartedItem[] = [
  { key: 'create-zone', to: '/app/zones', moduleKey: 'zones' },
  { key: 'add-equipment', to: '/app/equipment', moduleKey: 'equipment' },
  { key: 'first-task', to: '/app/tasks', moduleKey: 'tasks' },
  { key: 'log-note', to: '/app/interactions', moduleKey: 'interactions' },
  // Le prérequis de tout le module Argent : sans compte déclaré et daté, aucun
  // contrôle ne porte sur l'argent du foyer.
  { key: 'declare-account', to: '/app/money/accounts', moduleKey: 'money_accounts' },
  { key: 'ask-agent', to: '/app/agent' },
  { key: 'invite-member', to: '/app/settings' },
];

/** Guides — pages transverses d'abord, puis un guide par module (ordre MODULES). */
export const TUTORIAL_GUIDES: TutorialGuide[] = [
  // `search` vit ici et pas dans un guide à lui : la palette n'a pas de page, elle
  // est dans la barre du haut de *toutes* les pages — le guide transverse du
  // tableau de bord est le seul endroit où elle se raconte sans deep-link menteur.
  { key: 'dashboard', Icon: LayoutDashboard, to: '/app/dashboard', stepIds: ['overview', 'activity', 'alerts', 'search'] },
  { key: 'agent', Icon: Sparkles, to: '/app/agent', stepIds: ['ask', 'citations', 'web', 'context', 'create', 'memory'] },
  { key: 'digest', Icon: Newspaper, to: '/app/digest', stepIds: ['preview', 'enable', 'sections'] },
  { key: 'recap', Icon: PartyPopper, to: '/app/recap', stepIds: ['what', 'story', 'chapters', 'appointment', 'frozen'] },
  { key: 'install', Icon: Smartphone, to: '/app/settings', stepIds: ['install', 'enable', 'badge'] },
  { key: 'zones', moduleKey: 'zones', to: '/app/zones', stepIds: ['create', 'hierarchy', 'read', 'find', 'order', 'navigate'] },
  // `service` juste après `add` : c'est le geste courant du module, et il dépend
  // d'un champ qu'on ne remplit qu'à la création (l'intervalle d'entretien).
  { key: 'equipment', moduleKey: 'equipment', to: '/app/equipment', stepIds: ['add', 'service', 'purchase', 'history'] },
  { key: 'electricity', moduleKey: 'electricity', to: '/app/electricity', stepIds: ['board', 'readings', 'analyze'] },
  { key: 'water', moduleKey: 'water', to: '/app/water', stepIds: ['readings', 'charts'] },
  { key: 'weather', moduleKey: 'weather', to: '/app/weather', stepIds: ['location', 'forecast', 'dashboard', 'alerts'] },
  { key: 'stock', moduleKey: 'stock', to: '/app/stock', stepIds: ['add', 'quantities', 'expiry'] },
  { key: 'shopping', moduleKey: 'shopping', to: '/app/shopping-list', stepIds: ['quickAdd', 'fromStock', 'suggestions', 'check', 'commit', 'agent'] },
  { key: 'chickens', moduleKey: 'chickens', to: '/app/chickens', stepIds: ['flock', 'eggs', 'events', 'chores', 'stats', 'media'] },
  { key: 'orchard', moduleKey: 'orchard', to: '/app/orchard', stepIds: ['subjects', 'journal', 'seasons', 'harvests', 'frost', 'agent'] },
  // `labels` d'abord, et c'est le point du guide : la chasse est le seul jeu du
  // produit qui ne se joue **pas** dans l'app. Sans étiquettes collées dans les
  // pièces, l'écran de composition est un formulaire qui ne mène nulle part.
  { key: 'games', moduleKey: 'games', to: '/app/games', stepIds: ['labels', 'compose', 'riddles', 'play', 'replay'] },
  { key: 'insurance', moduleKey: 'insurance', to: '/app/insurance', stepIds: ['contracts', 'documents'] },
  { key: 'tasks', moduleKey: 'tasks', to: '/app/tasks', stepIds: ['create', 'organize', 'weather', 'complete', 'privacy'] },
  { key: 'projects', moduleKey: 'projects', to: '/app/projects', stepIds: ['create', 'plan', 'photos', 'budget'] },
  { key: 'interactions', moduleKey: 'interactions', to: '/app/interactions', stepIds: ['log', 'types', 'link', 'privacy'] },
  { key: 'trackers', moduleKey: 'trackers', to: '/app/trackers', stepIds: ['create', 'entries', 'charts'] },
  // Module « Argent » (parcours 26). Le premier guide explique **comment l'app
  // raisonne** — les trois suivants expliquent quoi cliquer. Cette séparation est
  // volontaire : le mécanisme de conformité a des règles contre-intuitives (une
  // fenêtre qui exclut volontairement des données, un zéro qui peut vouloir dire
  // « non évaluable ») qu'aucun parcours procédural ne fait comprendre.
  { key: 'money', moduleKey: 'money_accounts', Icon: ShieldCheck, to: '/app/money/accounts?tab=control', stepIds: ['source', 'allocation', 'axes', 'window', 'arbitrate', 'notEvaluable', 'cash'] },
  { key: 'expenses', moduleKey: 'money_expenses', Icon: Receipt, to: '/app/money/accounts?tab=pending', stepIds: ['record', 'supplier', 'sort', 'control', 'sources', 'sheet', 'trace', 'review'] },
  { key: 'budget', moduleKey: 'money_budgets', Icon: PiggyBank, to: '/app/money/budgets', stepIds: ['create', 'assign', 'track', 'sheet', 'analysis', 'recurring', 'report'] },
  { key: 'banking', moduleKey: 'money_accounts', Icon: Landmark, to: '/app/money/accounts', stepIds: ['accounts', 'cash', 'openingBalance', 'import', 'journal', 'balance', 'sheet'] },
  { key: 'documents', moduleKey: 'documents', to: '/app/documents', stepIds: ['upload', 'link', 'find', 'privacy'] },
  // `sort` vient juste après `browse` : l'intention est la première question que
  // pose désormais la galerie, avant même « où est rangée cette photo ».
  { key: 'photos', moduleKey: 'photos', to: '/app/photos', stepIds: ['browse', 'sort', 'add', 'phone', 'file'] },
  { key: 'directory', moduleKey: 'directory', to: '/app/directory', stepIds: ['contacts', 'structures'] },
  { key: 'alerts', Icon: AlertCircle, to: '/app/alerts', stepIds: ['review', 'act'] },
  { key: 'settings', Icon: User, to: '/app/settings', stepIds: ['profile', 'household', 'invite', 'modules', 'capabilities'] },
];

/** Clé de progression d'un guide, telle que stockée sur l'utilisateur. */
export function guideDoneKey(key: string): string {
  return `guide.${key}`;
}

/** Clé de progression d'un item de checklist. */
export function startDoneKey(key: string): string {
  return `start.${key}`;
}

const MODULE_ICONS = new Map(MODULES.map((m) => [m.key, m.Icon]));

function resolveIcon(guide: TutorialGuide): LucideIcon {
  // L'icône explicite gagne sur celle du module. Depuis que « Argent » réunit
  // comptes, dépenses et budgets (parcours 26), trois guides partagent un même
  // `moduleKey` : sans cette priorité ils afficheraient la même icône, et la liste
  // des guides ne se parcourrait plus du regard.
  if (guide.Icon) return guide.Icon;
  if (guide.moduleKey) {
    const icon = MODULE_ICONS.get(guide.moduleKey);
    if (icon) return icon;
  }
  return Sparkles;
}

/** Icône par guide — l'explicite si elle existe, sinon celle du module.
 *  Précalculé au chargement pour garder des références de composant stables. */
export const GUIDE_ICONS: Record<string, LucideIcon> = Object.fromEntries(
  TUTORIAL_GUIDES.map((g) => [g.key, resolveIcon(g)]),
);

export function findGuide(key: string | undefined): TutorialGuide | undefined {
  return TUTORIAL_GUIDES.find((g) => g.key === key);
}
