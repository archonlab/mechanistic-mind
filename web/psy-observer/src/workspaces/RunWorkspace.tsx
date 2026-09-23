import { memo } from 'react';
import { WorldPane } from '../chrome/WorldPane';
import { useFrameStore, useStatusStore } from '../observer/useExternalStore';

type Prefs = {
  layer: string;
  worldView: string;
  renderMode: string;
  opacity: number;
  showGrid: boolean;
  layers: Record<string, boolean>;
  trajectoryLength: number;
};

type Props = {
  prefs: Prefs;
  onSelectCell?: (info: any) => void;
  onSelectAgent?: (index: number) => void;
  mapKey?: number;
};

export const RunWorkspace = memo(function RunWorkspace({
  prefs, onSelectCell, onSelectAgent, mapKey,
}: Props) {
  const status = useStatusStore();
  const frame = useFrameStore();
  const agents = frame?.agents_observer || [];
  const physical = frame?.physical || {};
  const selected = status.selectedAgentId || 'agent_0';
  return (
    <div className="run-workspace" data-testid="workspace-run" data-workspace="RUN">
      <div className="sim-map-host">
        <WorldPane prefs={prefs} onSelectCell={onSelectCell} mapKey={mapKey} />
      </div>
      <footer className="sim-hud">
        {(agents.length ? agents : [{ observer_id: selected, selected_action: physical.selected_action }]).map((a: any, i: number) => {
          const id = a.observer_id || a.agent_id || `agent_${i}`;
          const active = id === selected;
          return (
            <button
              key={id}
              type="button"
              className={`agent-sel agent-chip ${active ? 'active' : ''}`}
              onClick={() => onSelectAgent?.(Number(String(id).replace(/\D/g, '') || i))}
            >
              <b>{String(id).toUpperCase()}</b>
              <span>{a.selected_action || physical.selected_action || '—'}</span>
            </button>
          );
        })}
        {status.undercoverIn && <span className="flag undercover in">EXPERIMENTER: IN WORLD</span>}
        {!status.undercoverIn && <span className="flag undercover out">EXPERIMENTER: NOT IN WORLD</span>}
        <span className="subtle">RUN · world + compact status</span>
      </footer>
    </div>
  );
});
