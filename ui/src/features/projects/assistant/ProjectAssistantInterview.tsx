import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles } from 'lucide-react';
import { Button } from '@/design-system/button';
import { Textarea } from '@/design-system/textarea';
import { FormField } from '@/design-system/form-field';
import type { AssistantQuestion, AssistantTurn } from '@/lib/api/projects';
import AnswerField from './AnswerField';

/**
 * L'entretien — une question à la fois, et une sortie toujours disponible.
 *
 * Deux choix d'écran portent tout le reste :
 *
 * - **« J'ai assez dit » est là dès la première question.** Ce n'est pas un
 *   raccourci pour les pressés, c'est la sortie qui empêche l'entretien de
 *   retenir quelqu'un qui a fini de parler. Un questionnaire dont on ne peut pas
 *   sortir se ferme par la croix, et le travail est perdu.
 * - **Une réponse illisible du modèle ne perd pas la question.** Le message
 *   d'erreur s'affiche *à côté* de la question précédente, qui reste posée : on
 *   reformule, on ne recommence pas.
 */

interface Props {
  goal: string;
  onGoalChange: (goal: string) => void;
  history: AssistantTurn[];
  question: AssistantQuestion | null;
  answer: string;
  onAnswerChange: (answer: string) => void;
  onStart: () => void;
  onAnswer: () => void;
  onFinish: () => void;
  isPending: boolean;
  asked: number;
  remaining: number;
  error: string | null;
}

export default function ProjectAssistantInterview({
  goal,
  onGoalChange,
  history,
  question,
  answer,
  onAnswerChange,
  onStart,
  onAnswer,
  onFinish,
  isPending,
  asked,
  remaining,
  error,
}: Props) {
  const { t } = useTranslation();
  const started = history.length > 0 || question !== null;

  return (
    <div className="space-y-4">
      {!started ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onStart();
          }}
          className="space-y-4"
        >
          <FormField label={t('projects.assistant.goalLabel')} htmlFor="assistant-goal">
            <Textarea
              id="assistant-goal"
              value={goal}
              onChange={(event) => onGoalChange(event.target.value)}
              rows={2}
              placeholder={t('projects.assistant.goalPlaceholder')}
              autoComplete="off"
            />
          </FormField>
          <p className="text-sm text-muted-foreground">{t('projects.assistant.intro')}</p>
          {error ? <ErrorNote message={error} /> : null}
          <Footer>
            <Button type="submit" disabled={isPending || goal.trim() === ''}>
              {isPending ? t('projects.assistant.thinking') : t('projects.assistant.start')}
            </Button>
          </Footer>
        </form>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onAnswer();
          }}
          className="space-y-4"
        >
          <p className="rounded-lg bg-muted p-3 text-sm text-foreground">{goal}</p>

          {history.length > 0 ? (
            <ul className="space-y-2">
              {history.map((turn, index) => (
                <li key={`${turn.field}-${index}`} className="text-sm">
                  <span className="text-muted-foreground">{turn.question}</span>
                  <br />
                  <span className="text-foreground">
                    {turn.answer || t('projects.assistant.noAnswer')}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          {error ? <ErrorNote message={error} /> : null}

          {question ? (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="flex items-start gap-2 text-sm font-medium text-foreground">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                  {question.text}
                </p>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t('projects.assistant.progress', {
                    asked: asked + 1,
                    total: asked + remaining,
                  })}
                </span>
              </div>
              {/* La fourchette de prix vit ici, à côté du champ — jamais dans le
                  champ. Un budget prévisionnel pré-rempli par le modèle est
                  indistinguable d'un budget décidé par le foyer, et il sert
                  ensuite de référence à la barre du chantier pendant des mois. */}
              {question.hint ? (
                <p className="text-xs text-muted-foreground">{question.hint}</p>
              ) : null}
              <AnswerField
                key={`${question.field}-${asked}`}
                inputId={`assistant-answer-${asked}`}
                question={question}
                value={answer}
                onChange={onAnswerChange}
                disabled={isPending}
              />
            </div>
          ) : null}

          <Footer>
            <Button type="button" variant="outline" onClick={onFinish} disabled={isPending}>
              {t('projects.assistant.enough')}
            </Button>
            <Button type="submit" disabled={isPending || !question}>
              {isPending ? t('projects.assistant.thinking') : t('projects.assistant.next')}
            </Button>
          </Footer>
        </form>
      )}
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive" role="alert">
      {message}
    </p>
  );
}

function Footer({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap justify-end gap-2 pt-2">{children}</div>;
}
