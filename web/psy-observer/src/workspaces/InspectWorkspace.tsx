import { memo, type ReactNode } from 'react';
import { WorldPane, type VolumeWorkspaceMode } from '../chrome/WorldPane';
import { InspectorDock } from '../inspectors/InspectorDock';
import type { InspectorId } from '../observer/stores';
import type { ObservationDestination } from '../observer/layoutShell';

type Prefs = {
  layer: string;
  worldView: string;
  renderMode: string;
  opacity: number;
  showGrid: boolean;
  layers: Record<string, boolean>;
  trajectoryLength: number;
};

type Extras = {
  experiment?: ReactNode;
  observeByTab?: Partial<Record<string, ReactNode>>;
  runs?: ReactNode;
  worldStatus?: ReactNode;
  sensors?: ReactNode;
  signals?: ReactNode;
};

type Props = {
  prefs: Prefs;
  mechanisms: any[];
  onToggleMechanism: (id: string, enabled: boolean) => void;
  onSetVisionRadius?: (radius: number) => void;
  onSetSurfaceDiscrimination?: (mode: 'OFF' | 'LOW' | 'RICH') => void;
  onSetOpticalMapping?: (mode: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM') => void;
  onSetSpatialVision?: (mode: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL') => void;
  onSelectCell?: (info: any) => void;
  expPressed?: string | null;
  mapKey?: number;
  extras?: Extras;
  onSectionTab?: (inspector: InspectorId, tab: string) => void;
  experimentApplyBar?: ReactNode;
  experimentMechanismDraft?: Record<string, boolean>;
  volumeWorkspace?: VolumeWorkspaceMode;
  onVolumeWorkspaceChange?: (mode: VolumeWorkspaceMode) => void;
  /** Researcher UI only — does not unmount InspectorDock content authority. */
  rightPanelOpen?: boolean;
  onToggleRightPanel?: () => void;
  /** S7C observation destination — when set to FPV/Hearing/Organism/Events, owns center. */
  observationDest?: ObservationDestination;
  /** Phenomenon-first central content (FPV / Hearing / Organism / Events). */
  observationCentral?: ReactNode;
};

function destOwnsCenter(dest?: ObservationDestination): boolean {
  return dest === 'FPV_VISION'
    || dest === 'HEARING'
    || dest === 'ORGANISM'
    || dest === 'EVENTS'
    || dest === 'SIMULATION_INFO'
    || dest === 'SCIENTIFIC_TOOLS';
}

export const InspectWorkspace = memo(function InspectWorkspace({
  prefs, mechanisms, onToggleMechanism, onSetVisionRadius, onSetSurfaceDiscrimination, onSetOpticalMapping, onSetSpatialVision, onSelectCell, expPressed, mapKey, extras, onSectionTab, experimentApplyBar, experimentMechanismDraft,
  volumeWorkspace = 'MAP',
  onVolumeWorkspaceChange,
  rightPanelOpen = true,
  onToggleRightPanel,
  observationDest,
  observationCentral,
}: Props) {
  const ownsCenter = destOwnsCenter(observationDest) && observationCentral != null;
  return (
    <div
      className={`inspect-workspace ${rightPanelOpen ? 'right-open' : 'right-closed'}`}
      data-testid="workspace-inspect"
      data-workspace="INSPECT"
      data-right-open={rightPanelOpen ? 'true' : 'false'}
      data-observation-dest={observationDest || 'WORLD'}
      data-center-owner={ownsCenter ? observationDest : 'WORLD_MAP'}
    >
      <div className="inspect-world">
        {ownsCenter ? (
          <div className="sim-observation-host" data-testid="observation-central-host">
            {observationCentral}
          </div>
        ) : (
          <div className="sim-map-host">
            <WorldPane
              prefs={prefs}
              onSelectCell={onSelectCell}
              mapKey={mapKey}
              showNearField
              volumeWorkspace={volumeWorkspace}
              onVolumeWorkspaceChange={onVolumeWorkspaceChange}
            />
          </div>
        )}
      </div>
      {!rightPanelOpen && onToggleRightPanel ? (
        <div className="shell-rail-affordance shell-rail-right" data-testid="right-panel-affordance">
          <button
            type="button"
            className="inspector-edge-toggle"
            data-testid="shell-toggle-right"
            aria-expanded={false}
            aria-controls="observer-right-inspector"
            title="Expand inspector"
            onClick={onToggleRightPanel}
          >
            <span aria-hidden="true">‹</span>
            <span>Inspector</span>
          </button>
        </div>
      ) : null}
      <div
        id="observer-right-inspector"
        className={`inspect-right-host ${rightPanelOpen ? 'is-open' : 'is-closed'}`}
        hidden={!rightPanelOpen}
        aria-hidden={!rightPanelOpen}
      >
        {rightPanelOpen && onToggleRightPanel ? (
          <div className="shell-panel-chrome">
            <span className="shell-panel-title">Context · Inspector</span>
            <button
              type="button"
              className="inspector-edge-toggle"
              data-testid="shell-toggle-right"
              aria-expanded={true}
              aria-controls="observer-right-inspector"
              title="Collapse inspector"
              onClick={onToggleRightPanel}
            >
              <span aria-hidden="true">›</span>
            </button>
          </div>
        ) : null}
        {/* Keep dock mounted when open; when closed use hidden+css so reopen restores scroll without remounting science. */}
        <div className="inspect-right-body" style={{ display: rightPanelOpen ? undefined : 'none' }}>
          <InspectorDock
            mechanisms={mechanisms}
            onToggleMechanism={onToggleMechanism}
            onSetVisionRadius={onSetVisionRadius}
            onSetSurfaceDiscrimination={onSetSurfaceDiscrimination}
            onSetOpticalMapping={onSetOpticalMapping}
            onSetSpatialVision={onSetSpatialVision}
            expPressed={expPressed}
            extras={extras}
            onSectionTab={onSectionTab}
            experimentApplyBar={experimentApplyBar}
            experimentMechanismDraft={experimentMechanismDraft}
          />
        </div>
      </div>
    </div>
  );
});
