import { memo } from 'react';
import { noteRender } from '../observer/stores';
import { useClockStore, useStatusStore } from '../observer/useExternalStore';

/** Isolated wall-clock — does not invalidate App or World. */
export const RuntimeClock = memo(function RuntimeClock() {
  noteRender('RuntimeClock');
  const now = useClockStore();
  const status = useStatusStore();
  if (!status.lastArrival || status.status !== 'RUNNING') return null;
  const age = now ? Math.max(0, (now - status.lastArrival) / 1000) : 0;
  const staleAfter = 2;
  const stale = age > staleAfter && status.connection === 'CONNECTED';
  return (
    <span
      className={`runtime-clock ${stale ? 'warn' : 'subtle'}`}
      title="Wall-clock age of last runtime heartbeat (not simulation time)"
    >
      {stale ? 'STALE' : ''}{stale ? ' · ' : ''}last hb {age.toFixed(1)}s
    </span>
  );
});
