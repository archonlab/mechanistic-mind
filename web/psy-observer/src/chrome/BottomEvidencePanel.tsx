import { memo, useState } from 'react';
import { useFrameStore, useStatusStore } from '../observer/useExternalStore';
import { layoutShellStore } from './layoutShellUi';
import type { ObservationDestination } from '../observer/layoutShell';

type Tab = 'status' | 'events' | 'evidence';

type Props = {
  /** Destination-aware secondary content — display only. */
  observationDest?: ObservationDestination;
};

/**
 * Intentional lower drawer (S7B/S7C) — live runtime only; not a fake continuous timeline.
 * Context-aware without duplicating primary destination content.
 */
export const BottomEvidencePanel = memo(function BottomEvidencePanel({
  observationDest = 'WORLD',
}: Props) {
  const status = useStatusStore();
  const frame = useFrameStore();
  const [tab, setTab] = useState<Tab>(
    observationDest === 'EVENTS' ? 'events' : 'status',
  );
  const tick = status.simTick ?? status.tick;
  const gen = status.runtimeGeneration;
  const events = (frame as any)?.recent_events || (frame as any)?.events || [];
  const recent = Array.isArray(events) ? events.slice(-8) : [];

  const contextHint =
    observationDest === 'ORGANISM' ? 'Organism primary view owns the center · drawer is secondary'
      : observationDest === 'HEARING' ? 'Hearing primary view owns the center · drawer is secondary'
        : observationDest === 'EVENTS' ? 'Full event stream is in the center · drawer shows a compact recent slice'
          : observationDest === 'FPV_VISION' ? 'FPV owns the center · drawer is secondary live status'
            : observationDest === 'SIMULATION_INFO' ? 'Simulation Info owns the center · drawer mirrors live status only'
              : 'Secondary live/evidence strip';

  return (
    <section
      id="observer-bottom-drawer"
      className="bottom-drawer"
      data-testid="bottom-evidence-panel"
      data-s7b-drawer="true"
      data-observation-dest={observationDest}
      aria-label="Status and evidence drawer"
    >
      <header className="bottom-drawer-handle">
        <button
          type="button"
          className="bottom-drawer-collapse"
          data-testid="drawer-collapse-toggle"
          aria-expanded={true}
          aria-controls="observer-bottom-drawer-body"
          title="Collapse drawer"
          onClick={() => layoutShellStore.patch({ bottomOpen: false })}
        >
          <span aria-hidden="true">▾</span>
          <span>Drawer</span>
        </button>
        <div className="bottom-drawer-tabs" role="tablist" aria-label="Drawer sections">
          {([
            ['status', 'Live Status'],
            ['events', 'Recent Events'],
            ['evidence', 'Evidence'],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? 'active' : ''}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="bottom-drawer-chip">t{tick ?? '—'} · gen {gen ?? '—'}</span>
      </header>
      <div id="observer-bottom-drawer-body" className="bottom-drawer-body">
        <p className="subtle" data-testid="bottom-context-hint">{contextHint}</p>
        {tab === 'status' ? (
          <div className="bottom-drawer-status" data-testid="bottom-tick">
            <span className={`badge ${String(status.status || '').toLowerCase()}`}>{status.status || '—'}</span>
            <span className="app-meta">{status.executionMode}</span>
            <span className="app-meta">{status.evidenceMode}</span>
            <span className="bottom-scientific-note" data-testid="bottom-scientific-boundary">
              Beta 4: scientific revalidation pending after physical support repair
            </span>
          </div>
        ) : null}
        {tab === 'events' ? (
          <div data-testid="bottom-recent-events">
            {recent.length === 0 ? (
              <span className="na">No recent event cards in live frame</span>
            ) : (
              <ul className="bottom-event-list">
                {recent.map((e: any, i: number) => (
                  <li key={i}>
                    {String(e?.type || e?.kind || e?.event_type || 'event')}
                    {e?.tick != null ? ` @${e.tick}` : ''}
                  </li>
                ))}
              </ul>
            )}
            <p className="subtle">Compact slice only — open Events destination for the bounded stream.</p>
          </div>
        ) : null}
        {tab === 'evidence' ? (
          <p className="app-meta" data-testid="bottom-evidence-tab">
            Live runtime ≠ saved evidence ≠ Analyzer reconstruction. Open Scientific Tools → Saved Runs / Analyzer for packages.
          </p>
        ) : null}
      </div>
    </section>
  );
});

/** Collapsed drawer handle — remains discoverable. */
export const BottomDrawerAffordance = memo(function BottomDrawerAffordance() {
  return (
    <div className="bottom-drawer-affordance" data-testid="bottom-panel-affordance">
      <button
        type="button"
        data-testid="drawer-expand-toggle"
        aria-expanded={false}
        aria-controls="observer-bottom-drawer"
        onClick={() => layoutShellStore.patch({ bottomOpen: true })}
      >
        <span aria-hidden="true">▴</span>
        <span>Show status drawer</span>
      </button>
    </div>
  );
});
