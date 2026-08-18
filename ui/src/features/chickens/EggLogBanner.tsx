import * as React from 'react';
import { Minus, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/design-system/card';
import { Button } from '@/design-system/button';
import { Input } from '@/design-system/input';
import { useEggStats, useLogEggs } from './hooks';
import { todayISO } from '@/lib/format';

function todayIsoDate(): string {
  return todayISO();
}

/**
 * The daily gesture: log today's egg count in two taps (US-3).
 * One log per day server-side — re-submitting replaces the count. A past date
 * can be picked for a forgotten day.
 */
export default function EggLogBanner() {
  const { t } = useTranslation();
  const { data: stats } = useEggStats();
  const logMutation = useLogEggs();

  const [date, setDate] = React.useState(todayIsoDate());
  const [count, setCount] = React.useState<number>(0);
  const isToday = date === todayIsoDate();

  // Seed the stepper with the already-logged value for today so +/- adjusts it.
  React.useEffect(() => {
    if (isToday && stats?.today != null) setCount(stats.today);
  }, [isToday, stats?.today]);

  function submit(next: number) {
    if (next < 0) return;
    setCount(next);
    logMutation.mutate({ date, count: next });
  }

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">
            {isToday ? t('chickens.eggs.today_question') : t('chickens.eggs.date_question')}
          </p>
          <Input
            type="date"
            value={date}
            max={todayIsoDate()}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 h-8 w-40 md:text-xs"
            aria-label={t('chickens.eggs.pick_date')}
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => submit(count - 1)}
            disabled={logMutation.isPending || count <= 0}
            aria-label={t('chickens.eggs.decrement')}
          >
            <Minus className="h-4 w-4" />
          </Button>
          <span className="min-w-[3.5rem] text-center text-2xl font-semibold tabular-nums text-foreground">
            {count} 🥚
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => submit(count + 1)}
            disabled={logMutation.isPending}
            aria-label={t('chickens.eggs.increment')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
