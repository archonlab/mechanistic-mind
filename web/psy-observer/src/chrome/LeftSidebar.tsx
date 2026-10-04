import { memo, useState } from 'react';
import type { DeviceTool } from '../desktop/types';
import {
  OBSERVATION_DESTINATIONS,
  type ObservationDestination,
} from '../observer/layoutShell';
import { applyRailDestination } from '../observer/railNav';
import { inspectorUiStore, openLeftHearingWorkspace, workspaceStore } from '../observer/stores';

type Props = {
  open: boolean;
  onToggleOpen: () => void;
  active: ObservationDestination;
  onActiveChange: (id: ObservationDestination) => void;
  onDeviceTool: (tool: DeviceTool) => void;
  pending?: boolean;
  selectedAgentLabel?: string;
};

const TOOL_NEST: { id: DeviceTool; label: string }[] = [
  { id: 'analyze', label: 'Analyzer' },
  { id: 'experiment', label: 'Experiment' },
  { id: 'sensors', label: 'Measurements' },
  { id: 'signals', label: 'Signals' },
  { id: 'intervention', label: 'Intervention' },
  { id: 'world_status', label: 'Authorities' },
  { id: 'runs', label: 'Saved Runs' },
];

function openExperimentInspectorTab(tabId: string, onDeviceTool: (tool: DeviceTool) => void) {
  const cur = workspaceStore.get();
  workspaceStore.set({
    ...cur,
    workspace: 'INSPECT',
    inspector: 'EXPERIMENT',
    inspectorOpen: true,
  });
  const ui = inspectorUiStore.get();
  inspectorUiStore.set({
    ...ui,
    tabs: { ...ui.tabs, EXPERIMENT: tabId },
  });
  onDeviceTool('experiment');
}

/**
 * Primary left observation navigation (S7B shell; S7C task-flow destinations).
 */
export const LeftSidebar = memo(function LeftSidebar({
  open,
  onToggleOpen,
  active,
  onActiveChange,
  onDeviceTool,
  pending = false,
  selectedAgentLabel = 'AGENT_0',
}: Props) {
  const [toolsOpen, setToolsOpen] = useState(active === 'SCIENTIFIC_TOOLS');

  const route = (id: ObservationDestination) => {
    onActiveChange(id);
    if (id === 'WORLD') {
      // Ordinary world setup (seed/size) — not World Status / Authorities.
      openExperimentInspectorTab('world', onDeviceTool);
    } else if (id === 'MODEL') {
      openExperimentInspectorTab('model', onDeviceTool);
    } else if (id === 'SIMULATION_INFO') {
      // Technical runtime status / measurements (not world preparation).
      const { nextWorkspace } = applyRailDestination('world_status', workspaceStore.get());
      workspaceStore.set(nextWorkspace);
      onDeviceTool('world_status');
    } else if (id === 'ORGANISM') {
      const { nextWorkspace } = applyRailDestination('observe', workspaceStore.get());
      workspaceStore.set(nextWorkspace);
      onDeviceTool('observe');
    } else if (id === 'FPV_VISION') {
      // Phase B: FPV owns the center — close narrow left dock (no FPV-in-sidebar).
      const ui = inspectorUiStore.get();
      inspectorUiStore.set({
        ...ui,
        leftSensoryMode: 'VISION',
        eyeDockMode: 'CLOSED',
      });
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    } else if (id === 'HEARING') {
      // Phase B: Hearing owns the center; keep engines via dock keep-alive when closed.
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
      onDeviceTool('signals');
    } else if (id === 'SCIENTIFIC_TOOLS') {
      setToolsOpen(true);
      // Landing owns center — do not auto-jump into Analyzer.
      const cur = workspaceStore.get();
      workspaceStore.set({ ...cur, workspace: 'INSPECT' });
    }
  };

  const pickTool = (tool: DeviceTool) => {
    onActiveChange('SCIENTIFIC_TOOLS');
    setToolsOpen(true);
    const { dest, nextWorkspace } = applyRailDestination(tool, workspaceStore.get());
    onDeviceTool(dest.deviceTool);
    workspaceStore.set(nextWorkspace);
  };

  return (
    <aside
      id="observer-left-rail"
      className={`left-sidebar ${open ? 'is-open' : 'is-collapsed'}`}
      data-testid="left-panel-host"
      data-s7b-sidebar="true"
      aria-label="Observation navigation"
    >
      <div className="left-sidebar-chrome">
        <button
          type="button"
          className="left-sidebar-collapse"
          data-testid="sidebar-collapse-toggle"
          aria-expanded={open}
          aria-controls="observer-left-nav"
          title={open ? 'Collapse navigation' : 'Expand navigation'}
          onClick={onToggleOpen}
        >
          <span aria-hidden="true">{open ? '‹' : '›'}</span>
          <span className="left-sidebar-collapse-label">{open ? 'Collapse' : 'Nav'}</span>
        </button>
        {open ? (
          <div className="left-sidebar-meta">
            <strong>Observe</strong>
            <span>{selectedAgentLabel}</span>
            {pending ? <span className="flag pending">PENDING</span> : null}
          </div>
        ) : null}
      </div>

      <nav id="observer-left-nav" className="left-sidebar-nav" data-testid="observation-nav">
        {OBSERVATION_DESTINATIONS.map((d) => (
          <div key={d.id} className="left-nav-block">
            <button
              type="button"
              data-testid={`obs-dest-${d.id}`}
              className={`left-nav-item ${active === d.id ? 'active' : ''}`}
              aria-pressed={active === d.id}
              title={d.label}
              onClick={() => {
                if (d.id === 'SCIENTIFIC_TOOLS') setToolsOpen((v) => (active === 'SCIENTIFIC_TOOLS' ? !v : true));
                route(d.id);
              }}
            >
              <span className="left-nav-glyph" aria-hidden="true">{glyph(d.id)}</span>
              {open ? <span className="left-nav-label">{d.label}</span> : null}
            </button>
            {open && d.id === 'SCIENTIFIC_TOOLS' && (toolsOpen || active === 'SCIENTIFIC_TOOLS') ? (
              <div className="left-nav-nested" role="group" aria-label="Scientific tools">
                {TOOL_NEST.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="left-nav-nested-item"
                    data-rail-tool={t.id}
                    onClick={() => pickTool(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </nav>
      {open ? (
        <p className="left-sidebar-footnote">
          Beta 4: scientific revalidation pending after physical support repair
        </p>
      ) : null}
    </aside>
  );
});

function glyph(id: ObservationDestination): string {
  switch (id) {
    case 'WORLD': return 'W';
    case 'MODEL': return 'M';
    case 'ORGANISM': return 'O';
    case 'FPV_VISION': return 'V';
    case 'HEARING': return 'H';
    case 'EVENTS': return 'E';
    case 'SIMULATION_INFO': return 'I';
    case 'SCIENTIFIC_TOOLS': return 'S';
    default: return '·';
  }
}
