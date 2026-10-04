/** S7C Scientific Tools landing — structured launcher, not an expanded dump. */

import type { DeviceTool } from '../desktop/types';

type ToolCard = {
  id: DeviceTool;
  label: string;
  purpose: string;
  designation: 'live' | 'saved' | 'research';
  mutatesDraft: boolean;
  readOnly: boolean;
};

const TOOLS: ToolCard[] = [
  { id: 'analyze', label: 'Analyzer', purpose: 'Saved-run scientific reconstruction and reports', designation: 'saved', mutatesDraft: false, readOnly: true },
  { id: 'experiment', label: 'Experiment', purpose: 'Shared experiment draft and Review/Apply', designation: 'research', mutatesDraft: true, readOnly: false },
  { id: 'sensors', label: 'Measurements', purpose: 'Live sensor / vision measurement panels', designation: 'live', mutatesDraft: false, readOnly: true },
  { id: 'signals', label: 'Signals', purpose: 'Live physical signal monitors', designation: 'live', mutatesDraft: false, readOnly: true },
  { id: 'intervention', label: 'Intervention/Ablations', purpose: 'Live interventions and ablation draft controls', designation: 'research', mutatesDraft: true, readOnly: false },
  { id: 'world_status', label: 'Authorities', purpose: 'Runtime authorities and status receipts', designation: 'live', mutatesDraft: false, readOnly: true },
  { id: 'runs', label: 'Saved Runs', purpose: 'Catalog of saved evidence packages', designation: 'saved', mutatesDraft: false, readOnly: true },
];

type Props = {
  onOpenTool: (tool: DeviceTool) => void;
};

export function ScientificToolsLanding({ onOpenTool }: Props) {
  return (
    <div
      className="scientific-tools-landing"
      data-testid="scientific-tools-landing"
      data-owns-center="true"
      aria-label="Scientific tools"
    >
      <header className="fpv-central-header">
        <strong>SCIENTIFIC TOOLS</strong>
        <span className="subtle">Structured launcher · existing destinations only</span>
      </header>
      <div className="tools-landing-grid" role="list">
        {TOOLS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="listitem"
            className="tools-landing-card"
            data-testid={`tools-card-${t.id}`}
            data-mutates-draft={String(t.mutatesDraft)}
            data-readonly={String(t.readOnly)}
            onClick={() => onOpenTool(t.id)}
          >
            <span className="tools-landing-title">{t.label}</span>
            <span className="subtle tools-landing-purpose">{t.purpose}</span>
            <span className="tools-landing-meta">
              <span className={`flag ${t.designation}`}>{t.designation.toUpperCase()}</span>
              <span className="subtle">{t.mutatesDraft ? 'may edit experiment draft' : 'read-only'}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export const SCIENTIFIC_TOOLS_LANDING_IDS = TOOLS.map((t) => t.id);
