import { ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { SettingsSection } from './SettingsSection';

const REPOSITORY_URL = 'https://github.com/jammindev/maisonnee';
const LICENSE_URL = `${REPOSITORY_URL}/blob/main/LICENSE`;

/**
 * Licence et lien vers le code source.
 *
 * Ce n'est pas une section « à propos » décorative : l'AGPL §13 impose qu'un
 * utilisateur qui interagit avec une instance à travers le réseau puisse en
 * obtenir la source. Une instance auto-hébergée sans ce lien n'est pas conforme.
 * D'où sa place dans les réglages, visible par tout membre du foyer, et pas
 * seulement dans un README que personne n'ouvre depuis l'app.
 */
export function AboutSection() {
  const { t } = useTranslation();

  return (
    <SettingsSection title={t('settings.about.title')} description={t('settings.about.description')}>
      <div className="space-y-3 text-sm">
        <p className="text-muted-foreground">{t('settings.about.license')}</p>
        <div className="flex flex-wrap gap-4">
          <a
            href={REPOSITORY_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 text-primary hover:underline"
          >
            {t('settings.about.sourceCode')}
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
          <a
            href={LICENSE_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 text-primary hover:underline"
          >
            {t('settings.about.licenseLink')}
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </div>
      </div>
    </SettingsSection>
  );
}
