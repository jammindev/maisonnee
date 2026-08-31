import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SheetDialog } from '@/design-system/sheet-dialog';
import type { AssistantQuestion, AssistantStep, AssistantTurn } from '@/lib/api/projects';
import { useAssistantStep, useCreateProjectFromPlan } from '../hooks';
import ProjectAssistantInterview from './ProjectAssistantInterview';
import ProjectAssistantReview from './ProjectAssistantReview';
import { type Draft, toDraft, toPayload } from './plan';

/**
 * L'entretien de création, de la première phrase au chantier créé.
 *
 * Tout l'état de l'entretien vit **ici**, dans ce composant, et nulle part
 * ailleurs : le serveur n'en garde rien et le renvoie à chaque tour. C'est ce qui
 * évite une table d'entretiens abandonnés à purger pour un geste de trois
 * minutes — au prix assumé qu'une fermeture perd l'entretien.
 *
 * Deux phases, une seule fenêtre. La bascule vers la relecture est déclenchée par
 * le **serveur** (`state === 'ready'`), jamais par un compte de questions tenu
 * ici : deux compteurs pour la même chose finiraient par se contredire, et c'est
 * celui du serveur qui décide.
 */

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ProjectAssistantDialog({ open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [goal, setGoal] = React.useState('');
  const [history, setHistory] = React.useState<AssistantTurn[]>([]);
  const [question, setQuestion] = React.useState<AssistantQuestion | null>(null);
  const [answer, setAnswer] = React.useState('');
  const [asked, setAsked] = React.useState(0);
  const [remaining, setRemaining] = React.useState(0);
  const [draft, setDraft] = React.useState<Draft | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const stepMutation = useAssistantStep();
  const createMutation = useCreateProjectFromPlan();

  // Remise à zéro à l'ouverture — jamais à la fermeture : vider pendant
  // l'animation de sortie ferait clignoter l'écran de relecture en « aucune
  // tâche » sous les yeux de l'utilisateur.
  React.useEffect(() => {
    if (!open) return;
    setGoal('');
    setHistory([]);
    setQuestion(null);
    setAnswer('');
    setAsked(0);
    setRemaining(0);
    setDraft(null);
    setError(null);
  }, [open]);

  const applyStep = (step: AssistantStep) => {
    setError(null);
    setAsked(step.asked);
    setRemaining(step.remaining);
    if (step.state === 'ready' && step.plan) {
      setDraft(toDraft(step.plan));
      setQuestion(null);
      return;
    }
    setQuestion(step.question ?? null);
    setAnswer('');
  };

  /**
   * Un tour raté ne perd **rien** : ni la question posée, ni la réponse tapée.
   *
   * L'historique n'est donc commité qu'au **succès**. La version naïve — écrire
   * l'historique avant l'appel — affichait la question deux fois quand le modèle
   * répondait de travers : une fois dans l'historique, une fois comme question
   * courante, puisque celle-ci n'avait pas été remplacée. L'utilisateur reformule
   * une erreur qui n'est pas la sienne ; il ne doit pas en plus la relire en
   * double.
   */
  const runStep = (nextHistory: AssistantTurn[], forceReady: boolean) => {
    stepMutation.mutate(
      { goal: goal.trim(), history: nextHistory, force_ready: forceReady },
      {
        onSuccess: (step) => {
          setHistory(nextHistory);
          applyStep(step);
        },
        onError: () => setError(t('projects.assistant.failed')),
      },
    );
  };

  const handleStart = () => runStep([], false);

  /** La question en cours, plus la réponse tapée — vide comprise : le serveur
   *  sait lire « je ne sais pas », et une question posée reste une question
   *  posée, qu'il ne faut pas reposer. */
  const withCurrentAnswer = (): AssistantTurn[] =>
    question
      ? [...history, { question: question.text, field: question.field, answer: answer.trim() }]
      : history;

  const handleAnswer = () => {
    if (!question) return;
    runStep(withCurrentAnswer(), false);
  };

  /**
   * « J'ai assez dit » emporte la réponse en cours si elle a été tapée.
   *
   * Sans ça, quelqu'un qui répond « 3 200 € » puis clique pour conclure voit son
   * montant disparaître — il a répondu, l'app l'oublie, et le plan sort sans
   * budget. C'est un raccourci vers la fin, pas un abandon de ce qui vient
   * d'être dit.
   */
  const handleFinish = () =>
    runStep(answer.trim() === '' ? history : withCurrentAnswer(), true);

  const handleCreate = () => {
    if (!draft) return;
    createMutation.mutate(toPayload(draft), {
      onSuccess: (project) => {
        onOpenChange(false);
        // On mène au chantier créé : « c'est fait » sans pouvoir aller voir est
        // invérifiable, et la page qu'on ouvre n'est justement pas vide.
        navigate(`/app/projects/${project.id}`);
      },
      onError: () => setError(t('common.saveFailed')),
    });
  };

  return (
    <SheetDialog
      open={open}
      onOpenChange={onOpenChange}
      title={
        draft ? t('projects.assistant.reviewTitle') : t('projects.assistant.title')
      }
    >
      {draft ? (
        <ProjectAssistantReview
          draft={draft}
          onDraftChange={setDraft}
          onBack={() => setDraft(null)}
          onCreate={handleCreate}
          isPending={createMutation.isPending}
          error={error}
        />
      ) : (
        <ProjectAssistantInterview
          goal={goal}
          onGoalChange={setGoal}
          history={history}
          question={question}
          answer={answer}
          onAnswerChange={setAnswer}
          onStart={handleStart}
          onAnswer={handleAnswer}
          onFinish={handleFinish}
          isPending={stepMutation.isPending}
          asked={asked}
          remaining={remaining}
          error={error}
        />
      )}
    </SheetDialog>
  );
}
