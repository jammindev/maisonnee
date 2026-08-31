import React, { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/lib/auth/useAuth';
import { api } from '@/lib/axios';
import { Button } from '../../design-system/button';
import { Input } from '../../design-system/input';
import { AuthShell } from './AuthShell';

/**
 * Where to land after login. Only same-site absolute paths are honoured — a
 * `next` pointing at another host would turn the login page into an open
 * redirect.
 */
function safeNext(raw: string | null): string {
  if (!raw) return '/app/dashboard';
  // Must be a single-slash absolute path. `//host` is protocol-relative, and
  // browsers normalise `\` to `/`, so `/\host` is the same trick spelled twice.
  if (!raw.startsWith('/') || raw.startsWith('//') || /[\\]/.test(raw)) return '/app/dashboard';
  return raw;
}

export default function LoginPage() {
  const { t } = useTranslation();
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const resetSuccess = (location.state as { resetSuccess?: boolean } | null)?.resetSuccess;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Une instance qui n'a aucun compte n'a pas d'écran de connexion à offrir :
  // aucun mot de passe ne l'ouvrira. On demande donc au serveur, et on redirige
  // vers la configuration initiale. `null` = pas encore de réponse ; afficher le
  // formulaire en attendant le ferait clignoter avant de disparaître.
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null);
  // Renseigné par la seule instance de démonstration publique. Partout ailleurs
  // le serveur renvoie `null`, et rien de tout ceci ne s'affiche.
  const [demo, setDemo] = useState<{ email: string; password: string } | null>(null);

  useEffect(() => {
    api
      .get<{ required: boolean; demo: { email: string; password: string } | null }>(
        '/accounts/setup/',
      )
      .then((res) => {
        setSetupRequired(res.data.required);
        setDemo(res.data.demo ?? null);
      })
      .catch(() => setSetupRequired(false));
  }, []);

  // Les identifiants de la démonstration sont **pré-remplis**, jamais contournés :
  // ce qui suit reste la connexion normale. Un bouton « entrer sans mot de passe »
  // livrerait à toutes les instances auto-hébergées un chemin d'authentification
  // sans identifiants, gardé par une seule variable d'environnement — un défaut
  // qu'on ne rattrape plus une fois l'image distribuée.
  useEffect(() => {
    if (!demo) return;
    setEmail((current) => current || demo.email);
    setPassword((current) => current || demo.password);
  }, [demo]);

  if (user) {
    navigate(next);
    return null;
  }

  if (setupRequired === null) return null;
  if (setupRequired) return <Navigate to="/setup" replace />;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(next);
    } catch {
      setError(t('auth.invalidCredentials'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t('auth.login')}
      subtitle={t('auth.loginSubtitle')}
      footer={
        <Link to="/forgot-password" className="text-primary hover:underline">
          {t('auth.forgotPassword')}
        </Link>
      }
    >
      {/* La vitrine dit ce qu'elle est, et où aller ensuite. Une démonstration
          qui ne renvoie pas vers l'installation garde un visiteur qu'elle
          n'avait pas vocation à garder : elle n'existe que pour ça. */}
      {demo ? (
        <div className="space-y-2 rounded-lg border border-primary/30 bg-primary/10 p-3 text-sm">
          <p className="font-medium text-foreground">{t('auth.demo.title')}</p>
          <p className="text-muted-foreground">{t('auth.demo.body')}</p>
          <p className="text-muted-foreground">{t('auth.demo.install')}</p>
          <pre className="overflow-x-auto rounded-md bg-background/70 p-2 text-xs text-foreground">
            <code>
              curl -O https://raw.githubusercontent.com/jammindev/maisonnee/main/docker-compose.yml{'\n'}
              docker compose up -d
            </code>
          </pre>
        </div>
      ) : null}
      {resetSuccess && <p className="text-sm text-primary">{t('auth.passwordResetSuccess')}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-3">
        <Input type="email" placeholder={t('auth.email')} value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" inputMode="email" />
        <Input type="password" placeholder={t('auth.password')} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? t('auth.loggingIn') : t('auth.submit')}
        </Button>
      </form>
    </AuthShell>
  );
}
