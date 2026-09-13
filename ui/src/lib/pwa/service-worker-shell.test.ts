import { describe, expect, it } from 'vitest';

// Le service worker est du JS servi tel quel par Django : il se lit comme une
// source, pas comme un module (il n'a pas de `export`, et son `self` n'existe
// pas ici).
import swSource from '../../../../templates/sw.js?raw';

/**
 * Le service worker ne garde pour coquille hors-ligne que des pages de l'app.
 *
 * Le pendant serveur du piège du PDF, et c'est **la même navigation** qui le
 * déclenche. `networkFirstShell` stockait *toute* réponse de navigation réussie
 * sous une clé unique (`__app_shell__`), en supposant que toute navigation est
 * une route du SPA. Ouvrir un document remplaçait donc la coquille hors-ligne
 * par… le PDF : l'app, relancée sans réseau, affichait le fichier au lieu du
 * tableau de bord.
 *
 * ⚠️ Corriger le lien ne suffit pas : un `<a download>` reste une **navigation**
 * du point de vue du service worker (Chromium lui passe l'événement avec
 * `mode: 'navigate'`). Sans cette garde, le correctif du lien poserait le
 * problème lui-même.
 *
 * Deux gardes indépendantes, et il faut les deux :
 *  - `/media/` n'est pas intercepté du tout — un fichier stocké doit descendre
 *    au navigateur tel quel ;
 *  - seule une réponse **HTML** devient la coquille, quel que soit le chemin.
 *
 * `templates/sw.js` n'a ni import ni build : il s'exécute ici dans un `self`
 * factice, et se teste donc tel qu'il sera servi.
 */

const ORIGIN = 'https://maison.test';

type FetchEvent = {
  request: Request;
  respondWith: (r: Response | Promise<Response>) => void;
};

function html(body = '<!doctype html><title>Maisonnée</title>') {
  return new Response(body, { status: 200, headers: { 'content-type': 'text/html; charset=utf-8' } });
}

function pdf() {
  return new Response('%PDF-1.4', { status: 200, headers: { 'content-type': 'application/pdf' } });
}

/** Exécute `templates/sw.js` dans un environnement de service worker minimal. */
function loadServiceWorker() {
  const listeners = new Map<string, ((event: unknown) => void)[]>();
  const buckets = new Map<string, Map<string, Response>>();

  const keyOf = (key: unknown) => (typeof key === 'string' ? key : (key as Request).url);

  const caches = {
    async open(name: string) {
      if (!buckets.has(name)) buckets.set(name, new Map());
      const bucket = buckets.get(name)!;
      return {
        async put(key: unknown, value: Response) {
          bucket.set(keyOf(key), value);
        },
        async match(key: unknown) {
          return bucket.get(keyOf(key));
        },
      };
    },
    async keys() {
      return [...buckets.keys()];
    },
    async delete(name: string) {
      return buckets.delete(name);
    },
    async match(key: unknown) {
      for (const bucket of buckets.values()) {
        const hit = bucket.get(keyOf(key));
        if (hit) return hit;
      }
      return undefined;
    },
  };

  /** Ce que le réseau répond, décidé par le test. */
  let network: (request: Request) => Promise<Response> = async () => html();

  const self = {
    location: { origin: ORIGIN },
    addEventListener(type: string, handler: (event: unknown) => void) {
      const list = listeners.get(type) ?? [];
      list.push(handler);
      listeners.set(type, list);
    },
    skipWaiting() {},
    clients: { claim() {}, matchAll: async () => [], openWindow: async () => null },
    registration: { showNotification: async () => {} },
    navigator: {},
  };

  new Function('self', 'caches', 'fetch', 'Response', 'URL', swSource)(
    self,
    caches,
    (request: Request) => network(request),
    Response,
    URL,
  );

  /** Simule une navigation ; renvoie ce que le SW a servi, ou null s'il s'est abstenu. */
  async function navigate(path: string, respond: () => Response) {
    network = async () => respond();
    const request = new Request(`${ORIGIN}${path}`);
    Object.defineProperty(request, 'mode', { value: 'navigate' });

    // Un tableau plutôt qu'une variable : `respondWith` écrit depuis une
    // closure, et TypeScript ne sait pas suivre cette écriture.
    const served: (Response | Promise<Response>)[] = [];
    const event: FetchEvent = { request, respondWith: (r) => void served.push(r) };
    for (const handler of listeners.get('fetch') ?? []) handler(event);
    return served.length === 0 ? null : await served[0];
  }

  /** Rejoue une navigation sans réseau — c'est le cas hors-ligne. */
  async function navigateOffline(path: string) {
    return navigate(path, () => {
      throw new Error('offline');
    });
  }

  return { navigate, navigateOffline };
}

describe('la coquille hors-ligne du service worker', () => {
  it("garde la page de l'app", async () => {
    const sw = loadServiceWorker();

    await sw.navigate('/app/dashboard', () => html());
    const offline = await sw.navigateOffline('/app/tasks');

    expect(offline).not.toBeNull();
    expect(await offline!.text()).toContain('Maisonnée');
  });

  it("ne se mêle pas d'un fichier stocké", async () => {
    const sw = loadServiceWorker();

    expect(await sw.navigate('/media/documents/foyer/contrat.pdf', () => pdf())).toBeNull();
  });

  it("n'est jamais remplacée par un fichier ouvert entre-temps", async () => {
    const sw = loadServiceWorker();

    await sw.navigate('/app/dashboard', () => html());
    await sw.navigate('/media/documents/foyer/contrat.pdf', () => pdf());

    const offline = await sw.navigateOffline('/app/dashboard');
    expect(offline).not.toBeNull();
    expect(await offline!.text()).toContain('Maisonnée');
  });

  it("n'est jamais remplacée par une réponse qui n'est pas une page", async () => {
    const sw = loadServiceWorker();

    await sw.navigate('/app/dashboard', () => html());
    // Une navigation dans l'app qui ne rend pas du HTML — un export, un flux.
    await sw.navigate('/app/quelque-chose.csv', () =>
      new Response('a,b\n1,2', { status: 200, headers: { 'content-type': 'text/csv' } }),
    );

    const offline = await sw.navigateOffline('/app/dashboard');
    expect(offline).not.toBeNull();
    expect(await offline!.text()).toContain('Maisonnée');
  });
});
