import { memo, useState, useSyncExternalStore } from 'react';
import { WorldMap } from '../components/WorldMap';
import { OccupancyVolumeView } from '../components/OccupancyVolumeView';
import { SurfaceLightView } from '../components/SurfaceLightView';
import { cameraFollowStore, inspectorUiStore, noteRender, tabVisibilityStore } from '../observer/stores';
import { useFrameStore } from '../observer/useExternalStore';

export type VolumeWorkspaceMode = 'MAP' | 'VOLUME' | 'SURFACE';

type DisplayPrefs = {
  layer: string;
  worldView: string;
  renderMode: string;
  opacity: number;
  showGrid: boolean;
  layers: Record<string, boolean>;
  trajectoryLength: number;
};

type Props = {
  prefs: DisplayPrefs;
  onHoverCell?: (info: any) => void;
  onSelectCell?: (info: any) => void;
  mapKey?: number;
  showNearField?: boolean;
  /** Single shared MAP/VOLUME/SURFACE mode (Observer UI only; never mutates simulation). */
  volumeWorkspace?: VolumeWorkspaceMode;
  onVolumeWorkspaceChange?: (mode: VolumeWorkspaceMode) => void;
};

function payloadMatchesMode(frame: any, mode: VolumeWorkspaceMode): boolean {
  const sub = frame?.observer_derived_payload_subscription
    || frame?.world?.observer_derived_payload_subscription
    || {};
  const included: string[] = sub.included_payload_families || [];
  if (mode === 'VOLUME') return included.includes('volume_occupancy_rendering');
  if (mode === 'SURFACE') return included.includes('surface_light_rendering');
  // MAP: require volume/surface NOT included (or absent subscription = legacy pending)
  if (included.length === 0 && sub.schema == null) return true;
  return !included.includes('volume_occupancy_rendering')
    && !included.includes('surface_light_rendering');
}

export const WorldPane = memo(function WorldPane({
  prefs,
  onHoverCell,
  onSelectCell,
  mapKey = 0,
  showNearField = false,
  volumeWorkspace = 'MAP',
  onVolumeWorkspaceChange,
}: Props) {
  noteRender('WorldPane');
  const frame = useFrameStore();
  const [hoverCell, setHoverCell] = useState<any>(null);
  const cameraFollow = useSyncExternalStore(
    cameraFollowStore.subscribe,
    cameraFollowStore.get,
    cameraFollowStore.get,
  );
  const fovOverlay = useSyncExternalStore(
    inspectorUiStore.subscribe,
    () => inspectorUiStore.get().fovOverlay,
    () => inspectorUiStore.get().fovOverlay,
  );
  const tabHidden = useSyncExternalStore(
    tabVisibilityStore.subscribe,
    tabVisibilityStore.get,
    tabVisibilityStore.get,
  );
  if (!frame) {
    return <div className="loading">Connecting to MM 1.0 — Tiktaalik…</div>;
  }
  const world = frame.world || {};
  const body = frame.body || {};
  const physical = frame.physical || {};
  const exp = frame.experimenter_interaction || {};
  const volumeDesc =
    (world as any).observer_camera_occupancy_consumer
    || { available: false, reason: 'MISSING' };
  const surfaceAudit =
    (world as any).researcher_physical_optical_audit_view
    || { available: false, status: 'UNAVAILABLE_NO_O2' };
  let followXY: { x: number; y: number } | null = null;
  if (cameraFollow === 'YOU') {
    const r = exp.last_realized || {};
    if (r.x != null && r.y != null) followXY = { x: Number(r.x), y: Number(r.y) };
  } else if (cameraFollow === 'TARGET') {
    const id = String(exp.target?.agent_id || '');
    const agents = frame.agents_observer || [];
    const a = agents.find((x: any) => String(x.agent_id || x.id) === id);
    const ax = a?.x ?? a?.body?.x;
    const ay = a?.y ?? a?.body?.y;
    if (ax != null && ay != null) followXY = { x: Number(ax), y: Number(ay) };
  }
  const showVolume = volumeWorkspace === 'VOLUME';
  const showSurface = volumeWorkspace === 'SURFACE';
  const payloadReady = payloadMatchesMode(frame, volumeWorkspace);
  // Never keep showing old-generation VOLUME/SURFACE geometry as current after mode switch.
  const pendingDerived = (showVolume || showSurface) && !payloadReady;
  const renderSuspended = Boolean(tabHidden) || pendingDerived;
  return (
    <div className="world-click-wrapper" data-testid="world-pane" data-volume-mode={volumeWorkspace}>
      <div
        className="toolbar-row world-viewport-mode-bar"
        data-testid="world-viewport-mode-bar"
        role="toolbar"
        aria-label="Main world viewport mode"
        style={{ gap: 8, flexWrap: 'wrap', padding: '6px 8px', alignItems: 'center' }}
      >
        <button
          type="button"
          data-testid="world-view-map"
          className={volumeWorkspace === 'MAP' ? 'active' : ''}
          aria-pressed={volumeWorkspace === 'MAP'}
          onClick={() => onVolumeWorkspaceChange?.('MAP')}
        >
          MAP / 2D
        </button>
        <button
          type="button"
          data-testid="world-view-volume"
          className={volumeWorkspace === 'VOLUME' ? 'active' : ''}
          aria-pressed={volumeWorkspace === 'VOLUME'}
          onClick={() => onVolumeWorkspaceChange?.('VOLUME')}
        >
          VOLUME / X-RAY
        </button>
        <button
          type="button"
          data-testid="world-view-surface"
          className={volumeWorkspace === 'SURFACE' ? 'active' : ''}
          aria-pressed={volumeWorkspace === 'SURFACE'}
          onClick={() => onVolumeWorkspaceChange?.('SURFACE')}
        >
          SURFACE / LIGHT
        </button>
        <span className="subtle" data-testid="world-viewport-mode-label">
          {volumeWorkspace === 'VOLUME'
            ? 'VOLUME / X-RAY · VW7 full occupancy · NOT ORGANISM VISION'
            : volumeWorkspace === 'SURFACE'
              ? 'SURFACE / LIGHT · O2/O3/O3A researcher transform · NOT ORGANISM VISION'
              : 'MAP / 2D · existing WorldMap'}
        </span>
        {pendingDerived ? (
          <span className="subtle" data-testid="world-viewport-payload-pending">
            Loading derived viewport payload…
          </span>
        ) : null}
        {tabHidden ? (
          <span className="subtle" data-testid="world-viewport-tab-hidden">
            Tab hidden · render suspended
          </span>
        ) : null}
      </div>
      {/* Absolute fill applies only inside this host — never over the mode bar. */}
      <div
        className="world-viewport-content-host"
        data-testid="world-viewport-content-host"
        data-active-renderer={showVolume ? 'VOLUME' : showSurface ? 'SURFACE' : 'MAP'}
        data-render-suspended={renderSuspended ? '1' : '0'}
      >
        <div className="world-layout map-only">
          <main className="world-center" data-testid="world-main-viewport">
            {showVolume ? (
              <OccupancyVolumeView
                renderDescription={pendingDerived ? { available: false, reason: 'PENDING_SUBSCRIPTION' } : volumeDesc}
                suspended={renderSuspended}
              />
            ) : showSurface ? (
              <SurfaceLightView
                audit={pendingDerived ? { available: false, status: 'PENDING_SUBSCRIPTION' } : surfaceAudit}
                suspended={renderSuspended}
              />
            ) : (
              <WorldMap
                key={mapKey}
                world={world}
                body={body}
                layer={prefs.layer}
                viewMode={prefs.worldView}
                perception={frame.perception}
                renderMode={prefs.renderMode}
                opacity={prefs.opacity}
                showGrid={prefs.showGrid}
                vectorDensity={0.35}
                contourLevels={8}
                autoScale
                scaleMin={0}
                scaleMax={1}
                compositeLayers={[prefs.layer, 'flow_mag']}
                trajectory={(frame.trajectory?.points || []).slice(-prefs.trajectoryLength)}
                layers={prefs.layers}
                geometryInterpretation={frame.geometry_interpretation}
                agentsObserver={frame.agents_observer || []}
                agentsViews={frame.agents_views || null}
                fovOverlay={fovOverlay}
                interactionTargetId={frame.experimenter_interaction?.target?.agent_id || null}
                nearFieldSensor={showNearField ? (physical?.near_field_exteroception || null) : null}
                followXY={followXY}
                onHoverCell={(c) => { setHoverCell(c); onHoverCell?.(c); }}
                onSelectCell={onSelectCell}
              />
            )}
            {!showVolume && !showSurface && hoverCell && (
              <div className="cell-chip">
                {hoverCell.field}[{hoverCell.ix},{hoverCell.iy}] = {hoverCell.value}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
});
