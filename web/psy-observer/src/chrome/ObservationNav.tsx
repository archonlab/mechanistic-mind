import { memo, useSyncExternalStore } from 'react';
import {
  OBSERVATION_DESTINATIONS,
  type ObservationDestination,
} from '../observer/layoutShell';
import { inspectorUiStore, openLeftHearingWorkspace, workspaceStore } from '../observer/stores';
import { applyRailDestination } from '../observer/railNav';

type Props = {
  active: ObservationDestination;
  onActiveChange: (id: ObservationDestination) => void;
  onDeviceTool?: (tool: string) => void;
};

/**
 * Routes product-level observation destinations onto existing workspace/rail/FPV authorities.
 */
export const ObservationNav = memo(function ObservationNav({
  active,
  onActiveChange,
  onDeviceTool,
}: Props) {
  // Keep store subscription so rail highlight stays coherent if workspace changes elsewhere.
  useSyncExternalStore(workspaceStore.subscribe, workspaceStore.get, workspaceStore.get);

  const route = (id: ObservationDestination) => {
    onActiveChange(id);
    if (id === 'WORLD') {
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'RUN' });
      onDeviceTool?.('home');
    } else if (id === 'ORGANISM') {
      const { nextWorkspace } = applyRailDestination('observe', workspaceStore.get());
      workspaceStore.set(nextWorkspace);
      onDeviceTool?.('observe');
    } else if (id === 'FPV_VISION') {
      const ui = inspectorUiStore.get();
      inspectorUiStore.set({
        ...ui,
        leftSensoryMode: 'VISION',
        eyeDockMode: 'CLOSED',
      });
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    } else if (id === 'HEARING') {
      openLeftHearingWorkspace();
      const ui = inspectorUiStore.get();
      inspectorUiStore.set({
        ...ui,
        leftSensoryMode: 'HEARING',
        eyeDockMode: 'CLOSED',
      });
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    } else if (id === 'EVENTS') {
      const { nextWorkspace } = applyRailDestination('signals', workspaceStore.get());
      workspaceStore.set(nextWorkspace);
      onDeviceTool?.('signals');
    } else if (id === 'SCIENTIFIC_TOOLS') {
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    }
  };

  return (
    <nav
      className="observation-nav"
      data-testid="observation-nav"
      aria-label="Observation destinations"
    >
      <span className="lab-kicker">OBSERVE</span>
      {OBSERVATION_DESTINATIONS.map((d) => (
        <button
          key={d.id}
          type="button"
          data-testid={`obs-dest-${d.id}`}
          className={active === d.id ? 'active' : ''}
          aria-pressed={active === d.id}
          onClick={() => route(d.id)}
        >
          {d.label}
        </button>
      ))}
    </nav>
  );
});
