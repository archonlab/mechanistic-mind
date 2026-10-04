/**
 * PSC MOTOR RESOLUTION — experiment control (not a science change).
 * Live path: GET/POST /api/config/psc-motor-resolution.
 * Deferred path: parent owns the draft; no network until Apply Experiment.
 */
import { useCallback, useEffect, useState } from 'react';
import { deferredMotorStatus, liveMotorStatus } from './pscUiAuthority.ts';

export type PscMotorResolution = 'LOCO_FACTORIZED' | 'OBSERVED_COMPOSITE';

type Props = {
  pscEnabled: boolean;
  refreshKey?: string | number;
  compact?: boolean;
  deferred?: boolean;
  mode?: PscMotorResolution;
  onModeChange?: (mode: PscMotorResolution) => void;
};

type ApiState = {
  psc_motor_resolution: string;
  experimental?: boolean;
  label?: string;
  history_reset?: boolean;
  smc_reset?: boolean;
  body_reset?: boolean;
  cognition_reset?: boolean;
};

function normalize(raw: string | undefined | null): PscMotorResolution {
  const s = String(raw || '').toUpperCase().replace(/[-\s]/g, '_');
  if (s === 'OBSERVED_COMPOSITE' || s === 'OBSERVEDCOMPOSITE') return 'OBSERVED_COMPOSITE';
  return 'LOCO_FACTORIZED';
}

export function PscMotorResolutionControl({
  pscEnabled, refreshKey, compact, deferred, mode: modeProp, onModeChange,
}: Props) {
  const [mode, setMode] = useState<PscMotorResolution>(modeProp || 'LOCO_FACTORIZED');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<ApiState | null>(null);

  const load = useCallback(async () => {
    if (deferred) return;
    try {
      const r = await fetch('/api/config/psc-motor-resolution');
      const j = (await r.json()) as ApiState;
      setMode(normalize(j.psc_motor_resolution));
      setLastOk(j);
      setError(null);
    } catch (e: any) {
      setError(String(e?.message || e || 'load failed'));
    }
  }, [deferred]);

  useEffect(() => {
    if (deferred) {
      if (modeProp) setMode(modeProp);
      return;
    }
    void load();
  }, [load, refreshKey, deferred, modeProp]);

  async function select(next: PscMotorResolution) {
    if (busy || next === mode) return;
    if (deferred) {
      setMode(next);
      onModeChange?.(next);
      return;
    }
    const prev = mode;
    setMode(next);
    setBusy(true);
    setError(null);
    try {
      const r = await fetch('/api/config/psc-motor-resolution', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next }),
      });
      const j = await r.json();
      if (!r.ok || j.accepted === false) {
        await load();
        setError('MOTOR RESOLUTION UPDATE FAILED');
        return;
      }
      const authoritative = normalize(j.psc_motor_resolution || j.new || next);
      setMode(authoritative);
      setLastOk({
        psc_motor_resolution: authoritative,
        experimental: authoritative === 'OBSERVED_COMPOSITE',
        history_reset: Boolean(j.history_reset),
        smc_reset: Boolean(j.smc_reset),
        body_reset: Boolean(j.body_reset),
        cognition_reset: Boolean(j.cognition_reset),
      });
      if (authoritative !== next) {
        setError('MOTOR RESOLUTION UPDATE FAILED');
      }
    } catch {
      setMode(prev);
      await load();
      setError('MOTOR RESOLUTION UPDATE FAILED');
    } finally {
      setBusy(false);
    }
  }

  const status = deferred
    ? deferredMotorStatus(pscEnabled)
    : liveMotorStatus({
        pscCurrentlyOn: pscEnabled,
        observedComposite: mode === 'OBSERVED_COMPOSITE',
      });

  const preserved =
    lastOk &&
    lastOk.history_reset === false &&
    lastOk.smc_reset === false &&
    lastOk.body_reset === false;

  return (
    <div className="psc-motor-resolution-control" style={{ marginTop: compact ? 4 : 8 }}>
      <div className="section-label">PSC MOTOR RESOLUTION</div>
      <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          type="button"
          className={mode === 'LOCO_FACTORIZED' ? 'active' : ''}
          disabled={busy}
          title="PSC competes primarily over locomotion; side-channel motor dimensions realize afterward."
          onClick={() => void select('LOCO_FACTORIZED')}
        >
          LOCO FACTORIZED
        </button>
        <button
          type="button"
          className={mode === 'OBSERVED_COMPOSITE' ? 'active' : ''}
          disabled={busy}
          title="PSC competes over empirically observed full composite motor signatures. Experimental."
          onClick={() => void select('OBSERVED_COMPOSITE')}
        >
          OBSERVED COMPOSITE
        </button>
        {mode === 'OBSERVED_COMPOSITE' && (
          <span className="flag" style={{ fontSize: 11 }}>EXPERIMENTAL</span>
        )}
      </div>
      {!compact && mode === 'OBSERVED_COMPOSITE' && (
        <div className="subtle" style={{ marginTop: 4 }}>
          Experimental full embodied candidate competition. Uses empirically observed
          composite motor signatures only.
        </div>
      )}
      <div className="metric" style={{ marginTop: 4 }}>
        <span>Status</span>
        <strong>{status}</strong>
      </div>
      {preserved && (
        <div className="subtle">
          History preserved · SMC preserved · Body preserved
        </div>
      )}
      {deferred && <div className="subtle">Draft only — applies with APPLY EXPERIMENT.</div>}
      {error && <div className="na">{error}</div>}
    </div>
  );
}

export default PscMotorResolutionControl;
