import * as React from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { Download, ExternalLink, Plus, RefreshCcw } from 'lucide-react';
import { Badge } from '@/design-system/badge';
import { Button } from '@/design-system/button';
import { Card, CardContent } from '@/design-system/card';
import ConfirmDialog from '@/components/ConfirmDialog';
import BackLink from '@/components/BackLink';
import PageHeader from '@/components/PageHeader';
import LoadError from '@/components/LoadError';
import ListSkeleton from '@/components/ListSkeleton';
import { TabShell } from '@/components/TabShell';
import { useNavigateBack, pushBack } from '@/lib/backNavigation';
import { formatFileSize } from '@/lib/api/documents';
import { formatDate } from '@/lib/format';
import {
  useDocument,
  useDeleteDocument,
  useReprocessDocumentOcr,
  documentKeys,
} from './hooks';
import DocumentEditDialog from './DocumentEditDialog';
import { useDelayedLoading } from '@/lib/useDelayedLoading';
import { useToast } from '@/lib/toast';

type Tab = 'info' | 'activity';
const TABS: Tab[] = ['info', 'activity'];

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const navigateBack = useNavigateBack('/app/documents');
  const qc = useQueryClient();
  const location = useLocation();

  const [editOpen, setEditOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);

  const { data: doc, isLoading, error } = useDocument(id ?? '');
  const deleteMutation = useDeleteDocument();
  const reprocessMutation = useReprocessDocumentOcr();
  const { toast } = useToast();

  const handleSaved = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: documentKeys.all });
  }, [qc]);

  const showSkeleton = useDelayedLoading(isLoading);

  function handleDelete() {
    if (!id) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigateBack(),
    });
  }

  function handleReprocess() {
    if (!id) return;
    reprocessMutation.mutate(id, {
      onSuccess: () =>
        toast({ description: t('documents.ocr.reprocessSuccess'), variant: 'success' }),
      onError: () =>
        toast({ description: t('documents.ocr.reprocessError'), variant: 'destructive' }),
    });
  }

  if (showSkeleton) {
    return <ListSkeleton className="space-y-2 p-4" />;
  }
  if (isLoading) return null;

  if (error || !doc) {
    return <LoadError message={t('documents.detail.not_found')} />;
  }

  const fileName = doc.name || doc.file_path.split('/').pop() || '';
  const fileSize =
    typeof doc.metadata?.size === 'number' ? formatFileSize(doc.metadata.size) : null;
  const ocrText = (doc.ocr_text || '').trim();
  const ocrMethod =
    typeof doc.metadata?.ocr_method === 'string' ? (doc.metadata.ocr_method as string) : null;
  const isImage = (doc.mime_type || '').startsWith('image/');
  const isPdf = doc.mime_type === 'application/pdf';
  const showOcrSection = isImage || isPdf || Boolean(ocrText);

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          backLink={<BackLink fallback="/app/documents" fallbackLabel={t('documents.title')} />}
          title={fileName}
          titleSuffix={
            doc.type && doc.type !== 'photo' ? (
              <Badge variant="secondary" className="text-xs">
                {t(`documents.type.${doc.type}`)}
              </Badge>
            ) : undefined
          }
          description={formatDate(doc.created_at)}
        >
          <Button
            type="button"
            variant="outline"
            className="h-8 px-3 text-sm"
            onClick={() => setEditOpen(true)}
          >
            {t('common.edit')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="h-8 px-3 text-sm"
            onClick={() => setDeleteOpen(true)}
          >
            {t('common.delete')}
          </Button>
        </PageHeader>

        {/* Tabs */}
        <TabShell<Tab>
          tabs={TABS.map((tab) => ({ key: tab, label: t(`documents.tabs.${tab}`) }))}
          sessionKey={`document-detail.${doc.id}.tab`}
          defaultTab="info"
        >
          {(tab) => (
            <>
              {tab === 'info' ? (
                <div className="space-y-4">
                  <Card>
                    <CardContent className="pt-4 space-y-2 text-sm">
                      {fileSize && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <span className="font-medium text-foreground">{fileSize}</span>
                        </div>
                      )}
                      {doc.mime_type && (
                        <div className="text-muted-foreground">
                          <span className="font-mono text-xs">{doc.mime_type}</span>
                        </div>
                      )}
                      {doc.notes && <p className="text-muted-foreground">{doc.notes}</p>}
                      {doc.file_url ? (
                        /* `download`, jamais `target="_blank"` : en PWA installée il n'y a
                           pas de barre de navigation, et `/media/…` est same-origin dans le
                           scope du manifeste — la fenêtre de l'app l'ouvrirait **sur place**,
                           sans rien pour revenir. Garde-fou :
                           `ui/src/lib/pwa/stored-file-links.test.ts`. */
                        <a
                          href={doc.file_url}
                          download
                          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                        >
                          <Download className="h-3.5 w-3.5" />
                          {t('documents.detail.download')}
                        </a>
                      ) : null}
                    </CardContent>
                  </Card>

                  {showOcrSection && (
                    <Card>
                      <CardContent className="pt-4">
                        <details className="group" {...(ocrText ? { open: true } : {})}>
                          <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium text-foreground">
                            <span>{t('documents.ocr.title')}</span>
                            {ocrMethod && ocrMethod !== 'skipped' && (
                              <Badge variant="outline" className="h-5 text-[10px]">
                                {ocrMethod}
                              </Badge>
                            )}
                          </summary>
                          <div className="mt-3 text-sm">
                            {ocrText ? (
                              <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-sans text-xs text-foreground">
                                {ocrText}
                              </pre>
                            ) : (
                              <p className="italic text-muted-foreground">
                                {t('documents.ocr.empty')}
                              </p>
                            )}
                            <div className="mt-3">
                              <Button
                                type="button"
                                variant="outline"
                                className="h-8 px-3 text-xs"
                                onClick={handleReprocess}
                                disabled={reprocessMutation.isPending}
                              >
                                <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
                                {reprocessMutation.isPending
                                  ? t('documents.ocr.reprocessing')
                                  : t('documents.ocr.reprocess')}
                              </Button>
                            </div>
                          </div>
                        </details>
                      </CardContent>
                    </Card>
                  )}
                </div>
              ) : null}

              {tab === 'activity' ? (
                <div className="space-y-4">
                  {(() => {
                    const backlinks = doc.entity_links.filter((l) => l.entity_type !== 'interaction');
                    if (backlinks.length === 0) return null;
                    return (
                      <div className="space-y-2">
                        <h2 className="text-base font-semibold text-foreground">
                          {t('documents.linked_to.title')}
                        </h2>
                        <ul className="space-y-2">
                          {backlinks.map((link) => (
                            <li key={`${link.entity_type}:${link.id}`}>
                              <Link
                                to={link.url_path}
                                state={pushBack(location)}
                                className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm hover:bg-muted/40"
                              >
                                <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                                  {link.label}
                                </span>
                                <Badge variant="outline" className="h-5 shrink-0 text-[10px]">
                                  {t(`documents.linked_to.types.${link.entity_type}`)}
                                </Badge>
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })()}

                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-foreground">
                      {t('documents.detail.linked_interactions')}
                    </h2>
                    <Link
                      to={`/app/interactions/new?source_document_id=${id}`}
                      className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      {t('documents.detail.add_activity')}
                    </Link>
                  </div>

                  {doc.linked_interactions.length === 0 ? (
                    <p className="text-sm italic text-muted-foreground">
                      {t('documents.detail.no_linked_interactions')}
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {doc.linked_interactions.map((item) => (
                        <li key={item.id} className="rounded-md border p-3 text-sm">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <span className="font-medium">{item.subject || '—'}</span>
                              {item.occurred_at && (
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                  {formatDate(item.occurred_at)}
                                </p>
                              )}
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              {item.type && (
                                <Badge variant="outline" className="h-5 text-[10px]">
                                  {t(`interactions.type.${item.type}`)}
                                </Badge>
                              )}
                              <Link
                                to={`/app/interactions/${item.id}`}
                                className="ml-1 inline-flex items-center text-xs text-muted-foreground hover:text-foreground"
                                aria-label={t('common.view')}
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                              </Link>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
            </>
          )}
        </TabShell>
      </div>

      <DocumentEditDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        doc={doc}
        onSaved={handleSaved}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t('common.confirmDelete')}
        description={t('documents.deleted')}
        onConfirm={handleDelete}
        loading={deleteMutation.isPending}
      />
    </>
  );
}
