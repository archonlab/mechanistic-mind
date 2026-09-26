/** Observer-only FOV visualization toggles — never a scientific mechanism. */

import { useSyncExternalStore } from 'react';
import { inspectorUiStore } from '../observer/stores';
import { SemanticChip } from './primitives';

export function FovOverlayControls({ agentIds }: { agentIds: string[] }) {
  const ui = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const fov = ui.fovOverlay;
  const ids = agentIds.length ? agentIds : ['agent_0'];
  const patch = (next: Partial<typeof fov>) => {
    inspectorUiStore.set({
      ...inspectorUiStore.get(),
      fovOverlay: { ...inspectorUiStore.get().fovOverlay, ...next },
    });
  };
  return (
    <section className="insp-acc" data-accordion="observer-fov">
      <div className="insp-acc-head" style={{ cursor: 'default' }}>
        OBSERVER OVERLAYS
        <SemanticChip kind="OBSERVER">OBSERVER ONLY</SemanticChip>
      </div>
      <div className="insp-acc-body">
        <div className="subtle">Map visualization of physical vision geometry. Not a mechanism. Not LOOK_AT / ATTENTION.</div>
        <div className="metric insp-metric" style={{ alignItems: 'center' }}>
          <span>Show field of view</span>
          <button
            type="button"
            className={fov.show ? 'active' : ''}
            onClick={() => patch({ show: !fov.show })}
          >
            {fov.show ? 'ON' : 'OFF'}
          </button>
        </div>
        <div className="metric insp-metric" style={{ alignItems: 'center' }}>
          <span>Sector attribution LEFT/FORWARD/RIGHT</span>
          <button
            type="button"
            className={fov.sectorAttribution ? 'active' : ''}
            disabled={!fov.show}
            onClick={() => {
              const next = !fov.sectorAttribution;
              patch({ sectorAttribution: next });
              void fetch('/api/observer/tiktaalik-eye', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ geometry_debug: next }),
              });
            }}
          >
            {fov.sectorAttribution ? 'ON' : 'OFF'}
          </button>
        </div>
        <div className="subtle">WORLD / SENSOR GEOMETRY DEBUG. Does not imply Tiktaalik receives cell coordinates.</div>
        <div className="section-label">Agents</div>
        {ids.map((id) => {
          const on = fov.agents[id] !== false;
          return (
            <label key={id} className="check" style={{ gap: 8 }}>
              <input
                type="checkbox"
                checked={on}
                disabled={!fov.show}
                onChange={(e) => patch({ agents: { ...fov.agents, [id]: e.target.checked } })}
              />
              {id.replace(/_/g, ' ').toUpperCase()}
            </label>
          );
        })}
      </div>
    </section>
  );
}
