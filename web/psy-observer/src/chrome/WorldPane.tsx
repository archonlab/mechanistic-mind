import { memo, useState, useSyncExternalStore } from 'react';
import { WorldMap } from '../components/WorldMap';
import { cameraFollowStore, inspectorUiStore, noteRender } from '../observer/stores';
import { useFrameStore } from '../observer/useExternalStore';

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
};

export const WorldPane = memo(function WorldPane({
  prefs, onHoverCell, onSelectCell, mapKey = 0, showNearField = false,
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
  if (!frame) {
    return <div className="loading">Connecting to MM 1.0 — Tiktaalik…</div>;
  }
  const world = frame.world || {};
  const body = frame.body || {};
  const physical = frame.physical || {};
  const exp = frame.experimenter_interaction || {};
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
  return (
    <div className="world-click-wrapper" data-testid="world-pane">
      <div className="world-layout map-only">
        <main className="world-center">
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
          {hoverCell && (
            <div className="cell-chip">
              {hoverCell.field}[{hoverCell.ix},{hoverCell.iy}] = {hoverCell.value}
            </div>
          )}
        </main>
      </div>
    </div>
  );
});
