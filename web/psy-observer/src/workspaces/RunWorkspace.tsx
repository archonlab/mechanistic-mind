import { memo, useEffect, useRef, useState } from 'react';
import { WorldPane } from '../chrome/WorldPane';
import { observerHudActionLabel } from '../observerHudAction';
import { useFrameStore, useStatusStore } from '../observer/useExternalStore';
import { recentHudApi } from '../recentSidechannelHud';

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
  'use no memo';
  const status = useStatusStore();
  const frame = useFrameStore();
  const recentStoreRef = useRef(recentHudApi.empty());
  const [recentClock, setRecentClock] = useState(0);
  const agents = frame?.agents_observer || [];
  const physical = frame?.physical || {};
  const selected = status.selectedAgentId || 'agent_0';
  const now = Date.now();
  const rows = (agents.length ? agents : [{ observer_id: selected, selected_action: physical.selected_action, composite_action_display: physical.composite_action_display }]);
  const labeled: { id: string; primary: string }[] = rows.map((a: any, i: number) => {
    const id = String(a.observer_id || a.agent_id || `agent_${i}`);
    const primary = observerHudActionLabel(a, physical.composite_action_display || physical.selected_action);
    return { id, primary };
  });
  const reduced = recentHudApi.reduce(recentStoreRef.current, {
    header: frame?.header,
    agents_observer: labeled.map((r: { id: string; primary: string }) => ({ observer_id: r.id, composite_action_display: r.primary })),
  }, now);
  recentStoreRef.current = reduced;
  const ingestKey = [
    recentHudApi.sessionKey(frame),
    frame?.header?.display_tick ?? frame?.header?.frame_tick ?? frame?.header?.tick ?? '',
    ...labeled.map((r: { id: string; primary: string }) => `${r.id}:${r.primary}`),
  ].join('~');

  useEffect(() => {
    const nxt = recentHudApi.nextExpiry(reduced, Date.now());
    if (nxt == null) return;
    const id = window.setTimeout(() => setRecentClock((n) => n + 1), Math.max(16, nxt - Date.now()));
    return () => window.clearTimeout(id);
  }, [ingestKey, recentClock, reduced]);

  return (
    <div className="run-workspace" data-testid="workspace-run" data-workspace="RUN">
      <div className="sim-map-host">
        <WorldPane prefs={prefs} onSelectCell={onSelectCell} mapKey={mapKey} />
      </div>
      <footer className="sim-hud">
        {labeled.map((row, i) => {
          const active = row.id === selected;
          const recent = recentHudApi.format(recentHudApi.visible(reduced, row.id, now));
          return (
            <span key={row.id} className="agent-chip-stack">
              <button
                type="button"
                className={`agent-sel agent-chip ${active ? 'active' : ''}`}
                onClick={() => onSelectAgent?.(Number(String(row.id).replace(/\D/g, '') || i))}
              >
                <b>{row.id.toUpperCase()}</b>
                <span>{row.primary}</span>
              </button>
              {recent ? <span className="recent-sidechannel">{recent}</span> : null}
            </span>
          );
        })}
        {status.undercoverIn && <span className="flag undercover in">EXPERIMENTER: IN WORLD</span>}
        {!status.undercoverIn && <span className="flag undercover out">EXPERIMENTER: NOT IN WORLD</span>}
        <span className="subtle">RUN · world + compact status</span>
      </footer>
    </div>
  );
});
