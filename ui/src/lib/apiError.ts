/**
 * Lit le message qu'une erreur d'API porte réellement.
 *
 * DRF répond soit `{"detail": "…"}` (permission, throttle, 404), soit
 * `{"<champ>": ["…"]}` (validation). Les deux formes disent quelque chose
 * d'utile — « Fichier trop volumineux (34 Mo). Maximum : 20 Mo. » — et sont
 * déjà traduites côté serveur.
 *
 * Sans ce helper, l'appelant fait un `catch {}` et affiche sa phrase générique :
 * l'app sait pourquoi elle a refusé et ne le dit pas, ce qui laisse
 * l'utilisateur réessayer à l'identique. Rendre `null` veut dire « le serveur
 * n'a rien dit d'exploitable » — à l'appelant de fournir son repli.
 */
export function apiErrorMessage(error: unknown): string | null {
  const data = (error as { response?: { data?: unknown } })?.response?.data;

  if (typeof data === 'string') {
    // Une page d'erreur HTML (nginx sur un 413/502) n'est pas un message.
    const trimmed = data.trim();
    return trimmed && !trimmed.startsWith('<') ? trimmed : null;
  }

  if (!data || typeof data !== 'object') return null;

  const record = data as Record<string, unknown>;
  const flatten = (value: unknown): string[] => {
    if (typeof value === 'string') return [value];
    if (Array.isArray(value)) return value.flatMap(flatten);
    return [];
  };

  // `detail` d'abord : quand DRF le pose, c'est LE message de l'erreur.
  const detail = flatten(record.detail);
  if (detail.length) return detail.join(' ');

  // Sinon les erreurs de champ, dans l'ordre du serveur.
  const fields = Object.entries(record)
    .filter(([key]) => key !== 'detail')
    .flatMap(([, value]) => flatten(value));

  return fields.length ? fields.join(' ') : null;
}
