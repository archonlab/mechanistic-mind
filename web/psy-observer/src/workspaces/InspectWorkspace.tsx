import { memo, type ReactNode } from 'react';
import { WorldPane } from '../chrome/WorldPane';
import { InspectorDock } from '../inspectors/InspectorDock';
import type { InspectorId } from '../observer/stores';

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
};

export const InspectWorkspace = memo(function InspectWorkspace({
  prefs, mechanisms, onToggleMechanism, onSetVisionRadius, onSetSurfaceDiscrimination, onSetOpticalMapping, onSetSpatialVision, onSelectCell, expPressed, mapKey, extras, onSectionTab,
}: Props) {
  return (
    <div className="inspect-workspace" data-testid="workspace-inspect" data-workspace="INSPECT">
      <div className="inspect-world">
        <div className="sim-map-host">
          <WorldPane
            prefs={prefs}
            onSelectCell={onSelectCell}
            mapKey={mapKey}
            showNearField
          />
        </div>
      </div>
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
      />
    </div>
  );
});
