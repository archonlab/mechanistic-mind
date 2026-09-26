import { useEffect, useRef, useState } from 'react';

type Interest = {
  preset?: string;
  products?: string[];
  note?: string;
};

const PRESETS = ['MINIMAL', 'NORMAL', 'FULL'] as const;

/** Optional products the experimenter can toggle (world/telemetry stay on). */
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

/**
 * Compact top-bar control: OBSERVER [ MINIMAL | NORMAL | FULL ]
 * Distinct from EVID [ FULL | COMPACT ]. Live instrumentation only.
 */
export function ObserverDetailControl() {
  const [interest, setInterest] = useState<Interest | null>(null);
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const refresh = async () => {
    try {
      const r = await fetch('/api/observer/detail');
      if (!r.ok) return;
      setInterest(await r.json());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  const applyInterest = (j: any) => {
    setInterest(j?.interest || j);
  };

  const setPreset = async (preset: string) => {
    setBusy(true);
    try {
      const r = await fetch('/api/observer/detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset }),
      });
      if (r.ok) applyInterest(await r.json());
    } finally {
      setBusy(false);
    }
  };

  const toggleProduct = async (product: string, enabled: boolean) => {
    setBusy(true);
    try {
      const r = await fetch('/api/observer/detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product, enabled }),
      });
      if (r.ok) applyInterest(await r.json());
    } finally {
      setBusy(false);
    }
  };

  const preset = (interest?.preset || 'NORMAL').toUpperCase();
  const products = new Set(interest?.products || []);

  return (
    <div
      ref={rootRef}
      className="observer-detail-topbar"
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 4 }}
      title="Live Observer instrumentation only — does not change evidence, mechanisms, or the organism"
    >
      <span className="subtle">OBSERVER</span>
      {PRESETS.map((p) => (
        <button
          key={p}
          type="button"
          disabled={busy}
          className={preset === p ? 'active' : undefined}
          onClick={() => setPreset(p)}
          title={
            p === 'MINIMAL'
              ? 'World + tick/TPS + mechanism status only'
              : p === 'NORMAL'
                ? 'Useful cognition panels, compact frames'
                : 'Full live introspection and graphs'
          }
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        disabled={busy}
        className={menuOpen ? 'active' : undefined}
        onClick={() => setMenuOpen((v) => !v)}
        title="Toggle optional live panels"
        aria-expanded={menuOpen}
      >
        Panels ▾
      </button>
      {menuOpen && (
        <div
          className="observer-detail-popover"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 40,
            marginTop: 4,
            minWidth: 220,
            maxHeight: 320,
            overflowY: 'auto',
            padding: '8px 10px',
            background: 'var(--panel-bg, #1a1d24)',
            border: '1px solid var(--border, #3a4050)',
            borderRadius: 6,
            boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
          }}
        >
          <div className="subtle" style={{ marginBottom: 6 }}>
            Optional live products (not evidence)
          </div>
          {OPTIONAL_PANELS.map((p) => {
            const on = products.has(p.id);
            return (
              <label
                key={p.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '3px 0',
                  cursor: busy ? 'wait' : 'pointer',
                  fontSize: 12,
                }}
              >
                <input
                  type="checkbox"
                  checked={on}
                  disabled={busy}
                  onChange={() => toggleProduct(p.id, !on)}
                />
                <span>{p.label}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
