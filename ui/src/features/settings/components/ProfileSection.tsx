import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, X, Check } from 'lucide-react';

import { Button } from '@/design-system/button';
import { Input } from '@/design-system/input';
import { Label } from '@/design-system/label';
import { SettingsSection } from './SettingsSection';
import { useToast } from '@/lib/toast';
import i18n from '@/lib/i18n';
import type { Locale } from '@/lib/api/users';
import { useCurrentUser, useUpdateProfile, useUploadAvatar, useDeleteAvatar } from '../hooks';

const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
];

export function ProfileSection() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const { data: user } = useCurrentUser();
  const updateProfile = useUpdateProfile();
  const uploadAvatar = useUploadAvatar();
  const deleteAvatar = useDeleteAvatar();

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [isEditing, setIsEditing] = React.useState(false);
  const [displayName, setDisplayName] = React.useState('');
  const [email, setEmail] = React.useState('');
  const [locale, setLocale] = React.useState<Locale>('en');

  // Sync form fields when user data changes or editing starts
  React.useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name ?? '');
    setEmail(user.email ?? '');
    setLocale((user.locale as Locale) ?? 'en');
  }, [user?.display_name, user?.email, user?.locale]);

  if (!user) return null;

  const initials = (user.full_name || user.email).slice(0, 2).toUpperCase();
  const localeLabel = LOCALE_OPTIONS.find((opt) => opt.value === locale)?.label;

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const prevLocale = user!.locale as Locale;
    const trimmedEmail = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      toast({ description: t('settings.emailInvalid'), variant: 'destructive' });
      return;
    }
    try {
      await updateProfile.mutateAsync({
        display_name: displayName.trim(),
        email: trimmedEmail,
        locale,
      });
      if (locale !== prevLocale) {
        localStorage.setItem('lang', locale);
        await i18n.changeLanguage(locale);
      }
      document.body.dispatchEvent(new CustomEvent('profile-updated'));
      toast({ description: t('settings.profileUpdated'), variant: 'success' });
      setIsEditing(false);
    } catch (err) {
      const data = (err as { response?: { data?: { email?: string[]; detail?: string } } })?.response?.data;
      const emailError = data?.email?.[0];
      toast({
        description: emailError || data?.detail || t('settings.requestFailed'),
        variant: 'destructive',
      });
    }
  }

  function handleCancel() {
    setDisplayName(user!.display_name ?? '');
    setEmail(user!.email ?? '');
    setLocale((user!.locale as Locale) ?? 'en');
    setIsEditing(false);
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast({ description: t('settings.avatarUnsupportedType'), variant: 'destructive' });
      return;
    }
    await uploadAvatar.mutateAsync(file);
    document.body.dispatchEvent(new CustomEvent('profile-updated'));
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleAvatarDelete() {
    await deleteAvatar.mutateAsync();
    document.body.dispatchEvent(new CustomEvent('profile-updated'));
  }

  const avatarUploading = uploadAvatar.isPending || deleteAvatar.isPending;
  const saving = updateProfile.isPending;

  return (
    <SettingsSection
      title={t('settings.profileTitle')}
      description={t('settings.displayNameDescription')}
      actions={
        !isEditing ? (
          <Button size="sm" variant="ghost" onClick={() => setIsEditing(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            {t('common.edit')}
          </Button>
        ) : null
      }
    >
      <div className="space-y-6">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          {user.avatar ? (
            <img
              src={user.avatar}
              alt={t('settings.avatarAlt')}
              className="h-20 w-20 rounded-full object-cover ring-2 ring-border"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted text-xl font-semibold ring-2 ring-border">
              {initials}
            </div>
          )}
          {isEditing && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{t('settings.avatarHelper')}</p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={avatarUploading}
                >
                  {avatarUploading ? t('settings.updating') : t('settings.avatarUpload')}
                </Button>
                {user.avatar && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleAvatarDelete()}
                    disabled={avatarUploading}
                  >
                    {t('settings.avatarRemove')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => void handleAvatarChange(e)}
        />

        {/* Read-only mode */}
        {!isEditing && (
          <div className="space-y-3">
            <div>
              <p className="text-base font-medium">{user.full_name || user.email}</p>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{localeLabel ?? locale}</p>
            </div>
          </div>
        )}

        {/* Edit mode */}
        {isEditing && (
          <form onSubmit={(e) => void handleSave(e)} className="space-y-4">
            <div>
              <Label className="mb-1">{t('settings.displayName')}</Label>
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={t('settings.displayNamePlaceholder')}
              />
            </div>
            <div>
              <Label className="mb-1">{t('settings.email')}</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('settings.emailPlaceholder')}
                autoComplete="email"
              />
            </div>
            <div>
              <Label className="mb-1">{t('settings.language')}</Label>
              <select
                value={locale}
                onChange={(e) => setLocale(e.target.value as Locale)}
                className="text-base w-full rounded-md border border-input bg-transparent px-3 py-2 md:text-sm"
              >
                {LOCALE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <Button size="sm" type="submit" disabled={saving}>
                <Check className="mr-2 h-4 w-4" />
                {saving ? t('settings.updating') : t('common.save')}
              </Button>
              <Button size="sm" type="button" variant="outline" onClick={handleCancel}>
                <X className="mr-2 h-4 w-4" />
                {t('common.cancel')}
              </Button>
            </div>
          </form>
        )}
      </div>
    </SettingsSection>
  );
}
