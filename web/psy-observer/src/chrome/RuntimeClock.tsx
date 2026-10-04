import { memo } from 'react';
import { noteRender } from '../observer/stores';
import { useClockStore, useStatusStore } from '../observer/useExternalStore';

type Props = {
  /** When true, only render a compact STALE/disconnected warning on the primary toolbar. */
  compact?: boolean;
  /** When true, always show heartbeat age text (More → Runtime information). */
  forceDetail?: boolean;
};

/** Isolated wall-clock — does not invalidate App or World. */
export const RuntimeClock = memo(function RuntimeClock({ compact = false, forceDetail = false }: Props) {
  noteRender('RuntimeClock');
  const now = useClockStore();
  const status = useStatusStore();
  if (!status.lastArrival) {
    if (forceDetail) return <span className="subtle">no heartbeat yet</span>;
    return null;
  }
  const age = now ? Math.max(0, (now - status.lastArrival) / 1000) : 0;
  const staleAfter = 2;
  const running = status.status === 'RUNNING';
  const stale = age > staleAfter && status.connection === 'CONNECTED' && running;
  const detail = `last hb ${age.toFixed(1)}s`;

  if (forceDetail) {
    return (
      <span
        className={`runtime-clock ${stale ? 'warn' : 'subtle'}`}
        data-testid="runtime-clock-detail"
        title="Wall-clock age of last runtime heartbeat (not simulation time)"
      >
        {stale ? 'STALE · ' : ''}{detail}
      </span>
    );
  }

  if (compact) {
    if (!stale) return null;
    return (
      <span
        className="runtime-clock warn"
        data-testid="runtime-clock-stale"
        role="status"
        aria-label={`Connection degraded: ${detail}`}
        title="Wall-clock age of last runtime heartbeat (not simulation time)"
      >
        STALE
      </span>
    );
  }

  // Legacy full mount: only while running (kept for any residual callers)
  if (!running) return null;
  return (
    <span
      className={`runtime-clock ${stale ? 'warn' : 'subtle'}`}
      title="Wall-clock age of last runtime heartbeat (not simulation time)"
    >
      {stale ? 'STALE' : ''}{stale ? ' · ' : ''}{detail}
    </span>
  );
});
