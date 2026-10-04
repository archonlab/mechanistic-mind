/** Prominent Vision enable + R1/R2/R3 experimenter control (Sensors). */

import { SettingInfoHelp } from './SettingInfoHelp';

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
  deferred?: boolean;
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
  deferred = false,
}: Props) {
  const cfgR = configuredRadius != null ? Number(configuredRadius) : runtimeRadius;
  const status = !visionMechanismPresent
    ? 'UNAVAILABLE'
    : mismatch
      ? (deferred ? 'UNAPPLIED' : 'MISMATCH')
      : 'READY';

  return (
    <div className="panel science-card" style={{ marginBottom: 8 }} data-testid="vision-experimenter-control">
      <h3>VISION</h3>
      <div className="metric" style={{ alignItems: 'center' }}>
        <span className="setting-label-row">
          Vision Enabled
          <SettingInfoHelp
            label="Vision Enabled"
            brief="Physical near-field optical transduction. Draft until APPLY when deferred."
            detail={
              <p>
                Toggles the vision mechanism in the experiment draft (deferred) or live authority.
                Does not claim camera imagery or human RGB.
              </p>
            }
            testId="info-vision-enabled"
          />
        </span>
        <button
          type="button"
          className={visionEnabled ? 'active' : ''}
          disabled={!onToggleVision || !visionMechanismPresent}
          title={!visionMechanismPresent ? 'Vision mechanism not in registry' : !onToggleVision ? 'Control not wired' : deferred ? 'Draft — applies with APPLY EXPERIMENT' : 'LIVE mutable'}
          onClick={() => onToggleVision?.()}
        >
          {visionEnabled ? 'ON' : 'OFF'}
        </button>
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span className="setting-label-row">
          Range
          <SettingInfoHelp
            label="Range"
            brief="Moore neighborhood radius R1–R3. Expands candidate cells only."
            detail={
              <p>
                {deferred
                  ? 'Changes stay in the experiment draft until global Apply (new run at tick 0).'
                  : 'LIVE change updates CONFIG + RUNTIME together. FOV / distance / illumination unchanged.'}
                {' '}Public Beta cap R3. R3 is not forced as a canonical public-model default in this repair.
              </p>
            }
            testId="info-vision-range"
          />
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {RADIUS.map((r) => (
            <button
              key={r}
              type="button"
              className={runtimeRadius === r ? 'active' : ''}
              disabled={!onSetRadius || !visionEnabled}
              aria-pressed={runtimeRadius === r}
              title={!onSetRadius ? 'Radius control not wired' : !visionEnabled ? 'Vision OFF — enable the mechanism first' : deferred ? `Draft Moore neighborhood R=${r}` : `LIVE — Moore neighborhood R=${r}`}
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
        <span>{deferred ? 'Draft range' : 'Runtime'}</span>
        <strong>R{runtimeRadius}</strong>
      </div>
      <div className="metric">
        <span>Status</span>
        <strong style={{ color: status === 'READY' ? undefined : '#b00020' }}>{status}</strong>
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span className="setting-label-row">
          Surface Discrimination
          <SettingInfoHelp
            label="Surface Discrimination"
            brief="OFF = intensity only. LOW/RICH add anonymous surface_c* channels."
            detail={
              <p>Not human RGB; not terrain labels. Agent-accessible optical channels through the existing FOV.</p>
            }
            testId="info-surface-discrimination"
          />
        </span>
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
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span className="setting-label-row">
          Optical Mapping
          <SettingInfoHelp
            label="Optical Mapping"
            brief="WORLD appearance mapping from deterministic seeds — not a cognition mode."
            detail={
              <p>
                Regenerates the optical tensor from experiment seed namespaces. Not a world-size reset,
                but observations change. Accessible surface_c* follow the new WORLD field.
              </p>
            }
            testId="info-optical-mapping"
          />
        </span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(['INDEPENDENT', 'CORRELATED', 'SHUFFLED', 'UNIFORM'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={opticalMapping === m ? 'active' : ''}
              disabled={!onSetOpticalMapping}
              aria-pressed={opticalMapping === m}
              title="Regenerates WORLD optical appearance from deterministic seeds."
              onClick={() => onSetOpticalMapping?.(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="metric" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }} data-testid="spatial-vision-control">
        <span className="setting-label-row">
          Spatial Vision
          <SettingInfoHelp
            label="Spatial Vision"
            brief="LEGACY exo bins vs A0–A4 spatial bins. OCCLUSION not forced canonical here."
            detail={
              <p>
                LEGACY keeps exo_0/1/2. ANGULAR / OCCLUSION / TEMPORAL_SPATIAL use spatial_exo_a* bins.
                Does not reset history. OCCLUSION is not established as a canonical public-model default in S7C.
              </p>
            }
            testId="info-spatial-vision"
          />
        </span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(['LEGACY', 'ANGULAR', 'OCCLUSION', 'TEMPORAL_SPATIAL'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={spatialVision === m ? 'active' : ''}
              disabled={!onSetSpatialVision || !visionEnabled}
              aria-pressed={spatialVision === m}
              title={!visionEnabled ? 'Vision OFF — enable the mechanism first' : deferred ? `Draft spatial_vision = ${m}` : `LIVE — near_field_exteroception.spatial_vision = ${m}`}
              onClick={() => onSetSpatialVision?.(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      {deferred ? (
        <div className="subtle" data-testid="experiment-draft-hint">
          Changes saved to experiment draft — current run unchanged
        </div>
      ) : null}
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
