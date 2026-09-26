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
  onSetSurfaceDiscrimination?: (mode: 'OFF' | 'LOW' | 'RICH') => void;
  onSetOpticalMapping?: (mode: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM') => void;
  onSetSpatialVision?: (mode: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL') => void;
  surfaceDiscrimination?: 'OFF' | 'LOW' | 'RICH';
  opticalMapping?: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM';
  spatialVision?: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL';
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
  onSetSurfaceDiscrimination,
  onSetOpticalMapping,
  onSetSpatialVision,
  surfaceDiscrimination = 'OFF',
  opticalMapping = 'INDEPENDENT',
  spatialVision = 'LEGACY',
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
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span>Surface discrimination</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['OFF', 'LOW', 'RICH'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={surfaceDiscrimination === m ? 'active' : ''}
              disabled={!onSetSurfaceDiscrimination || !visionEnabled}
              aria-pressed={surfaceDiscrimination === m}
              title={!visionEnabled ? 'Vision OFF — enable the mechanism first' : `Agent-accessible optical channels: ${m}`}
              onClick={() => onSetSurfaceDiscrimination?.(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="subtle">
        OFF matches Beta 3 (exo_* intensity only). LOW/RICH add anonymous surface_c* channels
        through the existing FOV. Not human RGB; not terrain labels.
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span>Optical mapping</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(['INDEPENDENT', 'CORRELATED', 'SHUFFLED', 'UNIFORM'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={opticalMapping === m ? 'active' : ''}
              disabled={!onSetOpticalMapping}
              aria-pressed={opticalMapping === m}
              title="Regenerates WORLD optical appearance from deterministic seeds. Does not reset tick/history. Accessible surface_c* will follow the new WORLD field."
              onClick={() => onSetOpticalMapping?.(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="subtle">
        Mapping is WORLD appearance, not a cognition mode. Apply regenerates the optical tensor
        (same experiment seed namespaces). Not a world-size reset, but observations change.
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }} data-testid="spatial-vision-control">
        <span>SPATIAL VISION</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(['LEGACY', 'ANGULAR', 'OCCLUSION', 'TEMPORAL_SPATIAL'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={spatialVision === m ? 'active' : ''}
              disabled={!onSetSpatialVision || !visionEnabled}
              aria-pressed={spatialVision === m}
              title={!visionEnabled ? 'Vision OFF — enable the mechanism first' : `LIVE — near_field_exteroception.spatial_vision = ${m}`}
              onClick={() => onSetSpatialVision?.(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="subtle">
        LEGACY keeps exo_0 / exo_1 / exo_2 (LEFT | FORWARD | RIGHT). ANGULAR / OCCLUSION /
        TEMPORAL_SPATIAL use canonical A0–A4 spatial_exo_a* bins. OCCLUSION and TEMPORAL_SPATIAL
        apply 2D nearest-in-sector occlusion on the same sampler. Does not reset history.
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
