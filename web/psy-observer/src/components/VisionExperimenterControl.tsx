/** Prominent Vision enable + R1/R2/R3 experimenter control (Sensors). */

type IntegrityRow = {
  mechanism?: string;
  configured?: boolean;
  runtime?: boolean;
  available?: boolean | null;
  status?: string;
  radius?: number | null;
  configured_radius?: number | null;
  runtime_radius?: number | null;
};

type Props = {
  visionEnabled: boolean;
  runtimeRadius: number;
  configuredRadius: number | null;
  mismatch: boolean;
  onToggleVision?: () => void;
  onSetRadius?: (radius: number) => void;
  visionMechanismPresent?: boolean;
};

const RADIUS = [1, 2, 3] as const;

export function VisionExperimenterControl({
  visionEnabled,
  runtimeRadius,
  configuredRadius,
  mismatch,
  onToggleVision,
  onSetRadius,
  visionMechanismPresent = true,
}: Props) {
  const cfgR = configuredRadius != null ? configuredRadius : runtimeRadius;
  const status = !visionMechanismPresent
    ? 'UNAVAILABLE'
    : mismatch
      ? 'MISMATCH'
      : 'READY';

  return (
    <div className="panel science-card" style={{ marginBottom: 8 }}>
      <h3>VISION</h3>
      <div className="subtle">Physical near-field optical transduction · Moore candidate radius</div>
      <div className="metric" style={{ alignItems: 'center' }}>
        <span>Enabled</span>
        <button
          type="button"
          className={visionEnabled ? 'active' : ''}
          disabled={!onToggleVision || !visionMechanismPresent}
          title={!visionMechanismPresent ? 'Vision mechanism not in registry' : !onToggleVision ? 'Control not wired' : 'LIVE mutable'}
          onClick={() => onToggleVision?.()}
        >
          {visionEnabled ? 'ON' : 'OFF'}
        </button>
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span>Range</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {RADIUS.map((r) => (
            <button
              key={r}
              type="button"
              className={runtimeRadius === r ? 'active' : ''}
              disabled={!onSetRadius || !visionEnabled}
              aria-pressed={runtimeRadius === r}
              title={!onSetRadius ? 'Radius control not wired' : !visionEnabled ? 'Vision OFF — enable the mechanism first' : `LIVE — Moore neighborhood R=${r}`}
              onClick={() => onSetRadius?.(r)}
            >
              R{r}
            </button>
          ))}
        </div>
      </div>
      <div className="metric">
        <span>Configured</span>
        <strong>R{cfgR}</strong>
      </div>
      <div className="metric">
        <span>Runtime</span>
        <strong>R{runtimeRadius}</strong>
      </div>
      <div className="metric">
        <span>Status</span>
        <strong style={{ color: status === 'READY' ? undefined : '#b00020' }}>{status}</strong>
      </div>
      <div className="subtle">
        R expands candidate cells only (Public Beta cap R3). FOV / distance / illumination unchanged.
        Default new experiment: R3. LIVE change updates CONFIG + RUNTIME together.
      </div>
    </div>
  );
}

export function visionRowFromIntegrity(integrity: any): IntegrityRow | null {
  const rows: IntegrityRow[] =
    integrity?.rows
    || integrity?.preflight?.rows
    || [];
  return rows.find((r) => r.mechanism === 'physical_near_field_vision') || null;
}
