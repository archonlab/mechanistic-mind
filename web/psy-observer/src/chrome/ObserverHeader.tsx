import { memo, useEffect, useRef, useSyncExternalStore } from 'react';
import { ObserverDetailControl } from '../components/ObserverDetailControl';
import { lifecycleErrorCode } from '../lifecycleReceipt';
import { frameStore, noteRender } from '../observer/stores';
import {
  useSetWorkspace,
  useStatusStore,
  useWorkspaceStore,
} from '../observer/useExternalStore';
import { RuntimeClock } from './RuntimeClock';
import { ThemeControl } from './ThemeControl';
import { checkpointNow, restoreCheckpoint, setCheckpointCadence } from '../api/client';

const SPEEDS = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 50];
const WORKSPACES = ['RUN', 'INSPECT', 'ANALYZE'] as const;

type Props = {
  onControl: (op: string, payload?: any) => void;
  onStop: () => void;
  disabled: boolean;
};

function StatusBadge({ value }: { value: string }) {
  return <span className={`badge ${String(value).toLowerCase().replaceAll(' ', '-')}`}>{value}</span>;
}

export const ObserverHeader = memo(function ObserverHeader({ onControl, onStop, disabled }: Props) {
  noteRender('ObserverHeader');
  const status = useStatusStore();
  const ws = useWorkspaceStore();
  const setWorkspace = useSetWorkspace();
  const onControlRef = useRef(onControl);
  onControlRef.current = onControl;
  const live = useSyncExternalStore(frameStore.subscribe, frameStore.getLive, () => null);
  const ck = (live && live.crash_checkpoint) || {};

  const displayStatus = status.connection === 'DISCONNECTED' ? 'DISCONNECTED' : status.status;
  const exec = String(status.executionMode || 'LIVE').toUpperCase();
  const evid = String(status.evidenceMode || 'FULL_SCIENTIFIC');
  const speed = status.simulationSpeed ?? 1;

  useEffect(() => {
    /* header does not own clock */
  }, []);

  return (
    <header className="lab-header" data-testid="observer-header">
      <div className="lab-brand">
        <strong>MM</strong>
        <span>{status.modelName || 'Tiktaalik'}</span>
        <span className="sep">·</span>
        <span className="subtle">Beta 3</span>
      </div>

      <div className="lab-cluster" aria-label="Simulation">
        <span className="lab-kicker">SIMULATION</span>
        <span className="lab-tick">t{status.simTick ?? status.tick ?? '—'}</span>
        <StatusBadge value={displayStatus} />
        {status.connection === 'DISCONNECTED' && (
          <span className="flag bad" title="Server unavailable — controls disabled">SERVER UNAVAILABLE</span>
        )}
      </div>

      <div className="lab-cluster transport-bar" aria-label="Actions">
        <span className="lab-kicker">ACTIONS</span>
        <button type="button" onClick={() => onControl('play')} disabled={disabled}>Play</button>
        <button type="button" onClick={() => onControl('pause')} disabled={disabled}>Pause</button>
        <button type="button" onClick={() => onControl('step', { n: 1 })} disabled={disabled}>Step</button>
        <button type="button" className="danger" onClick={onStop} disabled={disabled} title="Requires confirmation">Stop</button>
        <button type="button" className="danger" onClick={() => {
          if (window.confirm('Reset runtime? This starts a new generation.')) onControl('reset');
        }} disabled={disabled}>Reset</button>
      </div>

      <div className="lab-cluster execution-bar" aria-label="Execution presentation">
        <span className="lab-kicker">EXECUTION</span>
        {(['LIVE', 'FAST', 'MAX', 'HEADLESS'] as const).map((m) => (
          <button
            key={m}
            type="button"
            className={exec === m ? 'active' : ''}
            disabled={disabled}
            title={m === 'HEADLESS' ? 'No live world capture — scientific ticks continue' : 'Presentation policy only'}
            onClick={() => onControl('execution-mode', { mode: m })}
          >{m === 'LIVE' ? 'REALTIME' : m}</button>
        ))}
        <select
          aria-label="Simulation speed"
          value={String(speed)}
          disabled={disabled}
          onChange={(e) => onControl('speed', { speed: +e.target.value })}
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>{s === 50 ? 'MAX' : `${s}×`}</option>
          ))}
        </select>
        <span className="subtle">
          {status.simTps != null && Number.isFinite(Number(status.simTps)) ? `${status.simTps} t/s` : '—'}
        </span>
      </div>

      <div className="lab-cluster" aria-label="Observer instrumentation">
        <ObserverDetailControl />
      </div>

      <div className="lab-cluster" aria-label="Evidence recording">
        <span className="lab-kicker">EVIDENCE</span>
        {(['FULL_SCIENTIFIC', 'SEARCH_COMPACT'] as const).map((m) => (
          <button
            key={m}
            type="button"
            className={evid === m ? 'active' : ''}
            disabled={disabled}
            onClick={() => onControl('evidence-mode', { mode: m })}
          >{m === 'SEARCH_COMPACT' ? 'COMPACT' : 'FULL SCI'}</button>
        ))}
      </div>

      <nav className="lab-cluster workspace-nav" aria-label="Workspace">
        <span className="lab-kicker">WORKSPACE</span>
        {WORKSPACES.map((w) => (
          <button
            key={w}
            type="button"
            className={ws.workspace === w ? 'active' : ''}
            data-workspace-tab={w}
            onClick={() => setWorkspace(w)}
          >{w}</button>
        ))}
      </nav>

      <div className="lab-cluster" aria-label="Crash checkpoint">
        <span className="lab-kicker">CHECKPOINT</span>
        <span className="subtle" title="Persistence infrastructure only">
          last t{ck.last_tick ?? '—'} · next {ck.next_tick ?? '—'} · {String(ck.state || ck.cadence || 'OFF')}
        </span>
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
        <button
          type="button"
          disabled={disabled}
          title="Write crash-safe checkpoint now"
          onClick={() => { void checkpointNow(); }}
        >NOW</button>
        <button
          type="button"
          disabled={disabled}
          title="Restore last committed checkpoint as a new scientific segment"
          onClick={() => {
            if (window.confirm('Restore last checkpoint? This starts a new scientific segment from the checkpoint tick.')) {
              void restoreCheckpoint();
            }
          }}
        >RESTORE</button>
      </div>

      <ThemeControl />
      <RuntimeClock />
    </header>
  );
});

export { lifecycleErrorCode };
