/** Single coherent top application toolbar (S7E compact primary). */

import { memo, useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { frameStore, noteRender } from '../observer/stores';
import {
  useSetWorkspace,
  useStatusStore,
  useWorkspaceStore,
} from '../observer/useExternalStore';
import { RuntimeClock } from './RuntimeClock';
import { ThemeControl } from './ThemeControl';
import { checkpointNow, restoreCheckpoint, setCheckpointCadence } from '../api/client';
import { layoutShellStore, useLayoutShell } from './layoutShellUi';
import { SettingInfoHelp } from '../components/SettingInfoHelp';
import { stopAllResearcherAudio } from '../acoustic/researcherAudio.ts';
import { silenceAllListeningModes } from '../acoustic/listeningModeOwner.ts';

const SPEEDS = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 50];
const WORKSPACES = ['RUN', 'INSPECT', 'ANALYZE'] as const;
const DENSITY_PRESETS = ['MINIMAL', 'NORMAL', 'FULL'] as const;

/** Optional live products formerly under the Panels menu. Migrated to More → Layout. */
const OPTIONAL_PANELS: { id: string; label: string }[] = [
  { id: 'cognition', label: 'Cognition' },
  { id: 'psc', label: 'PSC' },
  { id: 'smc', label: 'SMC' },
  { id: 'historical_sensorimotor_selection', label: 'Historical SM' },
  { id: 'geometry', label: 'Geometry' },
  { id: 'graphs', label: 'Graphs' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'signals', label: 'Signals' },
  { id: 'signal_sensorimotor', label: 'Signal→PSC' },
  { id: 'experimenter', label: 'Experimenter' },
  { id: 'prediction', label: 'Prediction' },
  { id: 'history', label: 'History' },
  { id: 'compression', label: 'Compression' },
];

type Props = {
  onControl: (op: string, payload?: any) => void;
  onStop: () => void;
  disabled: boolean;
};

function StatusBadge({ value }: { value: string }) {
  return <span className={`badge ${String(value).toLowerCase().replaceAll(' ', '-')}`}>{value}</span>;
}

type Interest = { preset?: string; products?: string[] };

export const ObserverHeader = memo(function ObserverHeader({ onControl, onStop, disabled }: Props) {
  noteRender('ObserverHeader');
  const status = useStatusStore();
  const ws = useWorkspaceStore();
  const setWorkspace = useSetWorkspace();
  const layout = useLayoutShell();
  const live = useSyncExternalStore(frameStore.subscribe, frameStore.getLive, () => null);
  const ck = (live && live.crash_checkpoint) || {};
  const [moreOpen, setMoreOpen] = useState(false);
  const [interest, setInterest] = useState<Interest | null>(null);
  const [densityBusy, setDensityBusy] = useState(false);
  const [exiting, setExiting] = useState(false);
  const moreRef = useRef<HTMLDivElement | null>(null);
  const moreBtnRef = useRef<HTMLButtonElement | null>(null);
  const moreMenuId = useId();

  const displayStatus = status.connection === 'DISCONNECTED' ? 'DISCONNECTED' : status.status;
  const exec = String(status.executionMode || 'LIVE').toUpperCase();
  const evid = String(status.evidenceMode || 'FULL_SCIENTIFIC');
  const speed = status.simulationSpeed ?? 1;
  const tick = status.simTick ?? status.tick;
  const simRate =
    status.simTps != null && Number.isFinite(Number(status.simTps))
      ? Number(status.simTps)
      : null;
  const pausedRate = String(status.status || '').toUpperCase() === 'PAUSED' || String(status.status || '').toUpperCase() === 'STOPPED';
  const density = String(interest?.preset || 'NORMAL').toUpperCase();
  const products = new Set(interest?.products || []);

  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch('/api/observer/detail');
        if (r.ok) {
          const j = await r.json();
          setInterest(j?.interest || j);
        }
      } catch { /* ignore */ }
    })();
  }, []);

  useEffect(() => {
    if (!moreOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setMoreOpen(false);
        moreBtnRef.current?.focus();
      }
    };
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (moreRef.current?.contains(t) || moreBtnRef.current?.contains(t)) return;
      setMoreOpen(false);
      moreBtnRef.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDoc);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDoc);
    };
  }, [moreOpen]);

  async function setDensityPreset(preset: string) {
    setDensityBusy(true);
    try {
      const r = await fetch('/api/observer/detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset }),
      });
      if (r.ok) {
        const j = await r.json();
        setInterest(j?.interest || j);
      }
    } finally {
      setDensityBusy(false);
    }
  }

  async function exitMmObserver() {
    const unsaved = document.querySelector('[data-apply-status="UNAPPLIED"]');
    if (unsaved) {
      const ok = window.confirm(
        'Exit MM Observer?\n\nUnsaved experiment draft changes will be discarded. '
        + 'Runtime execution and any active analysis will stop.',
      );
      if (!ok) return;
    } else {
      const ok = window.confirm(
        'Exit MM Observer?\n\nRuntime execution and any active analysis will stop.',
      );
      if (!ok) return;
    }
    setExiting(true);
    setMoreOpen(false);
    try {
      silenceAllListeningModes();
      stopAllResearcherAudio();
    } catch { /* continue */ }
    try {
      await fetch('/api/instance/shutdown', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
    } catch { /* supervisor still owns shutdown */ }
  }

  async function toggleProduct(product: string, enabled: boolean) {
    setDensityBusy(true);
    try {
      const r = await fetch('/api/observer/detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product, enabled }),
      });
      if (r.ok) {
        const j = await r.json();
        setInterest(j?.interest || j);
      }
    } finally {
      setDensityBusy(false);
    }
  }

  const measuredLabel = pausedRate
    ? '0 sim/s'
    : simRate != null
      ? `${simRate} sim/s`
      : 'sim/s —';

  return (
    <header
      className="app-toolbar s7e-toolbar"
      data-testid="observer-header"
      data-s7b-toolbar="true"
      data-s7e-toolbar="true"
      role="banner"
      aria-label="Observer primary toolbar"
    >
      <div className="app-toolbar-left" aria-label="Product identity">
        <div className="app-brand">
          <strong>Mechanistic Mind</strong>
          <span className="app-brand-sub">Observer</span>
        </div>
        <span className="app-toolbar-sep" aria-hidden="true" />
        <div className="app-model-chip" title="Active public model / runtime">
          <span className="app-model-name">{status.modelName || 'Tiktaalik'}</span>
          <StatusBadge value={displayStatus} />
          {status.connection === 'DISCONNECTED' && (
            <span className="flag bad" role="status">SERVER UNAVAILABLE</span>
          )}
          <RuntimeClock compact />
        </div>
        <nav className="workspace-seg" aria-label="Workspace">
          {WORKSPACES.map((w) => (
            <button
              key={w}
              type="button"
              className={ws.workspace === w ? 'active' : ''}
              data-workspace-tab={w}
              aria-pressed={ws.workspace === w}
              onClick={() => setWorkspace(w)}
            >
              {w}
            </button>
          ))}
        </nav>
      </div>

      <div className="app-toolbar-center" aria-label="Simulation transport and speed">
        <div className="toolbar-transport-stack" data-testid="toolbar-transport-stack">
          <div className="transport-group" role="group" aria-label="Transport">
            <button type="button" className="transport-primary" onClick={() => onControl('play')} disabled={disabled}>
              Play
            </button>
            <button type="button" onClick={() => onControl('pause')} disabled={disabled}>Pause</button>
            <button type="button" onClick={() => onControl('step', { n: 1 })} disabled={disabled}>Step</button>
            <button type="button" className="danger" onClick={onStop} disabled={disabled} title="Requires confirmation">
              Stop
            </button>
            <button
              type="button"
              className="danger"
              disabled={disabled}
              onClick={() => {
                if (window.confirm('Reset runtime? This starts a new generation.')) onControl('reset');
              }}
            >
              Reset
            </button>
          </div>
          <div
            className="app-tick toolbar-metric"
            data-testid="app-toolbar-tick"
            aria-label={`Simulation tick ${tick ?? 'unavailable'}`}
          >
            tick {tick ?? '—'}
          </div>
        </div>

        <div className="toolbar-speed-stack" data-testid="toolbar-speed-stack">
          <label className="toolbar-speed-label">
            <span className="subtle">Speed</span>
            <select
              className="app-speed"
              data-testid="toolbar-speed-selector"
              aria-label="Execution speed profile"
              value={exec === 'LIVE' || exec === 'FAST' || exec === 'MAX' || exec === 'HEADLESS' ? exec : 'LIVE'}
              disabled={disabled}
              onChange={(e) => onControl('execution-mode', { mode: e.target.value })}
            >
              <option value="LIVE">Realtime</option>
              <option value="FAST">Fast</option>
              <option value="MAX">Max</option>
              <option value="HEADLESS">Headless</option>
            </select>
          </label>
          <div
            className="app-meta toolbar-metric"
            data-testid="toolbar-sim-rate"
            title="Measured simulation tick rate (not browser frame rate)"
            aria-label={`Measured rate ${measuredLabel}`}
          >
            {measuredLabel}
          </div>
        </div>
      </div>

      <div className="app-toolbar-right" aria-label="Shell controls">
        <div className="panel-toggles" role="group" aria-label="Panel visibility">
          <button
            type="button"
            data-testid="toolbar-toggle-right"
            aria-expanded={layout.rightOpen}
            aria-controls="observer-right-inspector"
            title={layout.rightOpen ? 'Collapse inspector' : 'Expand inspector'}
            onClick={() => layoutShellStore.patch({ rightOpen: !layout.rightOpen })}
          >
            Inspector
          </button>
          <button
            type="button"
            data-testid="toolbar-toggle-bottom"
            aria-expanded={layout.bottomOpen}
            aria-controls="observer-bottom-drawer"
            title={layout.bottomOpen ? 'Collapse drawer' : 'Expand drawer'}
            onClick={() => layoutShellStore.patch({ bottomOpen: !layout.bottomOpen })}
          >
            Drawer
          </button>
        </div>
        <ThemeControl />
        <div className="app-more" ref={moreRef}>
          <button
            ref={moreBtnRef}
            type="button"
            data-testid="toolbar-more"
            aria-expanded={moreOpen}
            aria-controls={moreMenuId}
            aria-haspopup="dialog"
            onClick={() => setMoreOpen((v) => !v)}
          >
            More
          </button>
          {moreOpen ? (
            <div
              id={moreMenuId}
              className="app-overflow-menu s7e-more-menu"
              role="dialog"
              aria-label="Secondary toolbar settings"
              data-testid="toolbar-more-menu"
            >
              <section className="more-group" data-testid="more-evidence-capture" aria-label="Evidence capture">
                <div className="more-group-title">
                  Evidence capture
                  <SettingInfoHelp
                    label="Evidence capture"
                    brief="Controls scientific evidence notebook capture mode."
                    detail="Does not change physics or cognition. Changing mode uses the existing live evidence-mode command."
                    testId="more-evidence-help"
                  />
                </div>
                <div className="more-seg" role="group">
                  {(['FULL_SCIENTIFIC', 'SEARCH_COMPACT'] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      className={evid === m ? 'active' : ''}
                      aria-pressed={evid === m}
                      disabled={disabled}
                      data-testid={`more-evidence-${m === 'SEARCH_COMPACT' ? 'compact' : 'full'}`}
                      onClick={() => onControl('evidence-mode', { mode: m })}
                    >
                      {m === 'SEARCH_COMPACT' ? 'Compact' : 'Full Scientific'}
                    </button>
                  ))}
                </div>
                <div className="subtle">Current: {evid === 'SEARCH_COMPACT' ? 'Compact' : 'Full Scientific'} · capture only</div>
              </section>

              <section className="more-group" data-testid="more-observer-density" aria-label="Observer density">
                <div className="more-group-title">
                  Observer density
                  <SettingInfoHelp
                    label="Observer density"
                    brief="Live UI/payload detail preset for the researcher Observer."
                    detail="Changes live frame detail and optional subscriptions only. Does not enter physics or cognition. Distinct from evidence capture."
                    testId="more-density-help"
                  />
                </div>
                <div className="more-seg" role="group">
                  {DENSITY_PRESETS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={density === p ? 'active' : ''}
                      aria-pressed={density === p}
                      disabled={densityBusy}
                      data-testid={`more-density-${p.toLowerCase()}`}
                      onClick={() => { void setDensityPreset(p); }}
                    >
                      {p === 'MINIMAL' ? 'Minimal' : p === 'NORMAL' ? 'Normal' : 'Full'}
                    </button>
                  ))}
                </div>
              </section>

              <section className="more-group" data-testid="more-execution-timing" aria-label="Execution timing">
                <div className="more-group-title">
                  Execution timing
                  <SettingInfoHelp
                    label="Wall-clock multiplier"
                    brief="Advanced override of wall-clock pacing only."
                    detail="Independent of the primary Speed profile (Realtime/Fast/Max/Headless). Does not change scientific tick numerics. Changing mode may also set speed via existing presets."
                    testId="more-multiplier-help"
                  />
                </div>
                <label className="more-row">
                  <span>Multiplier</span>
                  <select
                    data-testid="more-speed-multiplier"
                    aria-label="Wall-clock speed multiplier"
                    value={SPEEDS.includes(Number(speed)) ? String(speed) : String(speed)}
                    disabled={disabled}
                    onChange={(e) => onControl('speed', { speed: +e.target.value })}
                  >
                    {!SPEEDS.includes(Number(speed)) ? (
                      <option value={String(speed)}>{Number(speed) === 50 ? 'MAX' : `${speed}×`}</option>
                    ) : null}
                    {SPEEDS.map((s) => (
                      <option key={s} value={s}>{s === 50 ? 'MAX' : `${s}×`}</option>
                    ))}
                  </select>
                </label>
                <div className="subtle">Requested {speed === 50 ? 'MAX' : `${speed}×`} · measured {measuredLabel}</div>
              </section>

              <section className="more-group" data-testid="more-layout-products" aria-label="Layout live products">
                <div className="more-group-title">
                  Layout · live products
                  <SettingInfoHelp
                    label="Live products"
                    brief="Optional live Observer products formerly under Panels."
                    detail="Researcher-local subscriptions. Shell layout remains via Inspector, Drawer, Eye dock, and left sidebar."
                    testId="more-layout-help"
                  />
                </div>
                <div className="more-product-list">
                  {OPTIONAL_PANELS.map((p) => {
                    const on = products.has(p.id);
                    return (
                      <label key={p.id} className="more-product-row">
                        <input
                          type="checkbox"
                          checked={on}
                          disabled={densityBusy}
                          onChange={() => { void toggleProduct(p.id, !on); }}
                        />
                        <span>{p.label}</span>
                      </label>
                    );
                  })}
                </div>
              </section>

              <section className="more-group" data-testid="more-runtime-info" aria-label="Runtime information">
                <div className="more-group-title">Runtime information</div>
                <div className="app-overflow-row">
                  <span>Connection</span>
                  <span className="app-meta">{status.connection || '—'}</span>
                </div>
                <div className="app-overflow-row">
                  <span>Heartbeat</span>
                  <span className="app-meta" data-testid="more-heartbeat-detail">
                    <RuntimeClock forceDetail />
                  </span>
                </div>
                <div className="app-overflow-row">
                  <span>Checkpoint</span>
                  <span className="app-meta">
                    last t{ck.last_tick ?? '—'} · {String(ck.state || ck.cadence || 'OFF')}
                  </span>
                </div>
                <select
                  aria-label="Checkpoint cadence"
                  disabled={disabled}
                  value={String(ck.cadence === 'OFF' || ck.cadence == null ? 0 : ck.cadence)}
                  onChange={(e) => { void setCheckpointCadence(Number(e.target.value)); }}
                >
                  <option value={0}>OFF</option>
                  <option value={1000}>1000</option>
                  <option value={2500}>2500</option>
                  <option value={5000}>5000</option>
                </select>
                <button type="button" disabled={disabled} onClick={() => { void checkpointNow(); }}>Checkpoint now</button>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    if (window.confirm('Restore last checkpoint? This starts a new scientific segment from the checkpoint tick.')) {
                      void restoreCheckpoint();
                    }
                  }}
                >
                  Restore checkpoint
                </button>
                <p className="subtle">Simulation Info destination holds fingerprints and run identity.</p>
              </section>

              <section className="more-group" data-testid="more-application-exit" aria-label="Application">
                <div className="more-group-title">Application</div>
                <button
                  type="button"
                  className="danger"
                  data-testid="more-exit-mm-observer"
                  accessKey="q"
                  onClick={() => { void exitMmObserver(); }}
                >
                  Exit MM Observer
                </button>
                <div className="subtle">Closes the application window and stops the local server.</div>
              </section>
            </div>
          ) : null}
        </div>
      </div>
      {exiting ? (
        <div
          className="mm-closing-overlay"
          data-testid="mm-closing-overlay"
          role="status"
          aria-live="polite"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10000,
            background: 'rgba(8,10,14,0.72)',
            color: '#f4f6f8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20,
          }}
        >
          Closing MM Observer…
        </div>
      ) : null}
    </header>
  );
});
