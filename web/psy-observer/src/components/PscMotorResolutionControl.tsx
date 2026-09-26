/**
 * PSC MOTOR RESOLUTION — experiment control (not a science change).
 * Authoritative state from GET/POST /api/config/psc-motor-resolution.
 */
import { useCallback, useEffect, useState } from 'react';

export type PscMotorResolution = 'LOCO_FACTORIZED' | 'OBSERVED_COMPOSITE';

type Props = {
  pscEnabled: boolean;
  /** Optional: parent can force a refresh key after reset/load */
  refreshKey?: string | number;
  compact?: boolean;
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

export function PscMotorResolutionControl({ pscEnabled, refreshKey, compact }: Props) {
  const [mode, setMode] = useState<PscMotorResolution>('LOCO_FACTORIZED');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<ApiState | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/config/psc-motor-resolution');
      const j = (await r.json()) as ApiState;
      setMode(normalize(j.psc_motor_resolution));
      setLastOk(j);
      setError(null);
    } catch (e: any) {
      setError(String(e?.message || e || 'load failed'));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function select(next: PscMotorResolution) {
    if (busy || next === mode) return;
    const prev = mode;
    setMode(next); // optimistic
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
        // restore authoritative
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

  const status = !pscEnabled
    ? mode === 'OBSERVED_COMPOSITE'
      ? 'READY — PSC OFF'
      : 'READY'
    : mode === 'OBSERVED_COMPOSITE'
      ? 'ACTIVE · EXPERIMENTAL'
      : 'ACTIVE';

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
      {error && <div className="na">{error}</div>}
    </div>
  );
}

export default PscMotorResolutionControl;
