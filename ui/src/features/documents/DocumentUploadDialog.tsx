import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X } from 'lucide-react';
import { SheetDialog } from '@/design-system/sheet-dialog';
import { Input } from '@/design-system/input';
import { Textarea } from '@/design-system/textarea';
import { Select } from '@/design-system/select';
import { Button } from '@/design-system/button';
import { FormField } from '@/design-system/form-field';
import { Label } from '@/design-system/label';
import { DOCUMENT_TYPES, type DocumentType, type DocumentDetail } from '@/lib/api/documents';
import { apiErrorMessage } from '@/lib/apiError';
import { useCreateDocument } from './hooks';
import ZonePicker from '@/features/zones/ZonePicker';

interface DocumentUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /**
   * Called after each successful upload — **une fois par document créé**, pas une
   * fois par lot : les appelants rattachent le fichier à leur entité ou invalident
   * leur cache document par document, et n'ont donc rien à changer pour recevoir
   * un lot.
   */
  onSaved: (created?: DocumentDetail) => void | Promise<void>;
  /** When set, hides the type selector and submits with this type. */
  forcedType?: 'photo';
  /**
   * Précision ajoutée au titre — la destination du fichier quand l'appelant en a
   * une (la phase « Avant / Pendant / Après » d'un onglet photos, par exemple).
   * Sans elle, tous les points d'entrée ouvraient le même dialog anonyme.
   */
  titleSuffix?: string;
}

export default function DocumentUploadDialog({
  open,
  onOpenChange,
  onSaved,
  forcedType,
  titleSuffix,
}: DocumentUploadDialogProps) {
  const { t } = useTranslation();
  const createDocument = useCreateDocument();
  const isPhotoMode = forcedType === 'photo';

  const [files, setFiles] = React.useState<File[]>([]);
  const [name, setName] = React.useState('');
  const [type, setType] = React.useState<DocumentType | 'photo' | ''>(forcedType ?? '');
  const [notes, setNotes] = React.useState('');
  const [zone, setZone] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);

  // Ce qui est **déjà arrivé** dans le foyer, par index dans `files`. C'est la
  // seule chose qui rend la relance sûre : réessayer après un échec au huitième
  // fichier ne doit pas recréer les sept premiers en doublon.
  const [done, setDone] = React.useState<Set<number>>(new Set());
  const [failed, setFailed] = React.useState<Set<number>>(new Set());
  const [progress, setProgress] = React.useState<{ current: number; total: number } | null>(null);
  const [uploading, setUploading] = React.useState(false);

  const isBatch = files.length > 1;

  React.useEffect(() => {
    if (!open) return;
    setFiles([]);
    setName('');
    setType(forcedType ?? '');
    setNotes('');
    setZone('');
    setError(null);
    setDone(new Set());
    setFailed(new Set());
    setProgress(null);
    setUploading(false);
  }, [open, forcedType]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    setFiles(picked);
    setError(null);
    // Une nouvelle sélection est un nouveau lot : ce qui était envoyé l'a été
    // sous d'autres fichiers, et le garder ferait sauter des envois.
    setDone(new Set());
    setFailed(new Set());
    if (picked.length === 1 && !name) {
      setName(picked[0].name.replace(/\.[^.]+$/, ''));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Le bouton est `disabled` pendant l'envoi, mais il n'est pas le seul chemin :
    // Entrée depuis un champ texte soumet aussi, et un second passage relirait un
    // `done` d'avant la première réponse — donc renverrait des fichiers en double.
    if (uploading) return;
    if (files.length === 0) {
      setError(t('documents.new.selectFile'));
      return;
    }
    setError(null);
    setUploading(true);

    const remaining = files.map((file, index) => ({ file, index })).filter(({ index }) => !done.has(index));
    const nextDone = new Set(done);
    const nextFailed = new Set<number>();
    // Ce que le serveur a répondu sur le premier échec. Il sait pourquoi il a
    // refusé — taille, type, débit — et le dit déjà dans la langue du lecteur ;
    // le taire laisse réessayer à l'identique.
    let serverMessage: string | null = null;

    // Séquentiel, jamais en parallèle : le serveur normalise l'image, lit l'EXIF
    // et génère les vignettes à chaque fichier. Vingt requêtes d'un coup, c'est
    // le foyer qui attend son propre import.
    for (const [position, { file, index }] of remaining.entries()) {
      setProgress({ current: position + 1, total: remaining.length });
      try {
        const response = await createDocument.mutateAsync({
          // Le nom saisi n'a de sens que pour un fichier seul — appliqué à un lot
          // il donnerait vingt documents homonymes. Au-delà, chacun garde le sien.
          file,
          name: files.length === 1 ? name || undefined : undefined,
          type: type || undefined,
          notes: notes || undefined,
          zone: zone || undefined,
        });
        nextDone.add(index);
        setDone(new Set(nextDone));
        await onSaved(response.document);
      } catch (err) {
        nextFailed.add(index);
        setFailed(new Set(nextFailed));
        serverMessage = serverMessage ?? apiErrorMessage(err);
      }
    }

    setUploading(false);
    setProgress(null);
    setFailed(nextFailed);

    if (nextFailed.size === 0) {
      onOpenChange(false);
      return;
    }
    const fallback =
      files.length === 1
        ? t('documents.uploadFailed')
        : t('documents.upload.someFailed', { count: nextFailed.size });
    setError(serverMessage ? `${fallback} ${serverMessage}` : fallback);
  };

  const baseTitle = isPhotoMode ? t('photos.upload_title') : t('documents.upload.title');
  const title = titleSuffix ? `${baseTitle} — ${titleSuffix}` : baseTitle;

  const typeOptions = [
    { value: '', label: t('documents.filter.allTypes') },
    ...DOCUMENT_TYPES.map((v) => ({
      value: v,
      label: t(`documents.type.${v}`),
    })),
  ];

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
    >
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
          )}

          {/* File input */}
          <div className="space-y-1.5">
            <Label htmlFor="upload-file">
              {t('documents.new.selectFiles')}
              <span className="ml-1 text-destructive">*</span>
            </Label>
            <Input
              id="upload-file"
              type="file"
              multiple
              accept={
                isPhotoMode
                  ? 'image/jpeg,image/png,image/gif,image/webp,image/heic,image/heif'
                  : 'image/jpeg,image/png,image/gif,image/webp,image/heic,image/heif,application/pdf'
              }
              onChange={handleFileChange}
              required
            />

            {files.length === 1 && (
              <p className="text-xs text-muted-foreground">
                {t('documents.new.selectedFile')}: {files[0].name}
              </p>
            )}

            {/* Le lot se lit fichier par fichier : sans ça, « 3 échecs » ne dit
                pas lesquels, et l'utilisateur ne peut ni relancer en confiance ni
                savoir ce qui manque dans sa galerie. */}
            {isBatch && (
              <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                {files.map((file, index) => (
                  <li
                    key={`${file.name}-${index}`}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span className="min-w-0 flex-1 truncate text-muted-foreground">{file.name}</span>
                    {done.has(index) ? (
                      <span className="flex shrink-0 items-center gap-1 text-primary">
                        <Check className="h-3 w-3" />
                        {t('documents.upload.fileDone')}
                      </span>
                    ) : failed.has(index) ? (
                      <span className="flex shrink-0 items-center gap-1 text-destructive">
                        <X className="h-3 w-3" />
                        {t('documents.upload.fileFailed')}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}

            {/* Un lot dit où il en est ; un fichier seul dit ce que le serveur
                fait de lui (OCR). Remplacer le second par le premier ferait
                disparaître le seul retour d'un PDF qui met dix secondes. */}
            {progress && progress.total > 1 ? (
              <p className="text-xs text-muted-foreground" role="status">
                {t('documents.upload.progress', {
                  current: progress.current,
                  total: progress.total,
                })}
              </p>
            ) : createDocument.isPending ? (
              <p className="text-xs text-muted-foreground" role="status">
                {t('documents.ocr.processing')}
              </p>
            ) : null}
          </div>

          {/* Name — un seul fichier seulement (voir handleSubmit) */}
          {!isBatch && (
            <FormField label={t('documents.fieldName')} htmlFor="upload-name">
              <Input
                id="upload-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('documents.upload.namePlaceholder')}
                autoComplete="off"
              />
            </FormField>
          )}

          {/* Type */}
          {!isPhotoMode && (
            <FormField label={t('documents.fieldType')} htmlFor="upload-type">
              <Select
                id="upload-type"
                value={type}
                onChange={(e) => setType(e.target.value as DocumentType | '')}
                options={typeOptions}
              />
            </FormField>
          )}

          {/* Zone */}
          <FormField label={t('documents.upload.zone')} htmlFor="upload-zone">
            <ZonePicker
              id="upload-zone"
              value={zone || null}
              onChange={(id) => setZone(id ?? '')}
              allowEmpty
              emptyLabel={t('documents.upload.noZone')}
            />
          </FormField>

          {/* Notes */}
          <FormField label={t('documents.fieldNotes')} htmlFor="upload-notes">
            <Textarea
              id="upload-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder={t('documents.fieldNotesPlaceholder')}
            />
          </FormField>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={uploading}>
              {uploading ? t('documents.new.submitting') : t('documents.upload.submit')}
            </Button>
          </div>
        </form>
    </SheetDialog>
  );
}
