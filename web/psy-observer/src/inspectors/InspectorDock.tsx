import { memo, type ReactNode, useSyncExternalStore } from 'react';
import { ActionDecisionInspector } from '../components/ActionDecisionInspector';
import { ContextualProspectiveControlPanel } from '../components/ContextualProspectiveControlPanel';
import { HistoricalSensorimotorSelectionPanel } from '../components/HistoricalSensorimotorSelectionPanel';
import { InteractPanel } from '../components/InteractPanel';
import { MechanismPreflightPanel } from '../components/MechanismPreflightPanel';
import { MechanismsPanel } from '../components/MechanismsPanel';
import { MotionCausalInspector } from '../components/MotionCausalInspector';
import { NearFieldSensorPanel } from '../components/NearFieldSensorPanel';
import { OscillatorySignalingPanel } from '../components/OscillatorySignalingPanel';
import { PscMotorResolutionControl } from '../components/PscMotorResolutionControl';
import { PscOffTicksControl } from '../components/PscOffTicksControl';
import { SensorimotorConsequencePanel } from '../components/SensorimotorConsequencePanel';
import { SignalSensorimotorPanel } from '../components/SignalSensorimotorPanel';
import { VestibularProprioceptionPanel } from '../components/VestibularProprioceptionPanel';
import { WhyDidItRotate } from '../components/WhyDidItRotate';
import { WhyDidItsShapeChange } from '../components/WhyDidItsShapeChange';
import {
  inspectorUiStore,
  noteRender,
  type InspectorId,
} from '../observer/stores';
import { useFrameStore, useStatusStore, useWorkspaceStore } from '../observer/useExternalStore';
import { overlayMechanismEnabled } from '../observer/experimentDraft';
import { InspectorAccordion, InspectorTabs, ReadOnlyMetric, SemanticChip } from './primitives';
import { FovOverlayControls } from './FovOverlayControls';

export const SECTION_TABS: Record<string, { id: string; label: string }[]> = {
  EXPERIMENT: [
    { id: 'world', label: 'World' },
    { id: 'ecology', label: 'Ecology' },
    { id: 'model', label: 'Model' },
    { id: 'body', label: 'Body' },
    { id: 'psc', label: 'PSC' },
    { id: 'ablations', label: 'Ablations' },
    { id: 'vision', label: 'Vision' },
    { id: 'review', label: 'Review / Apply' },
  ],
  SENSORS: [
    { id: 'vision', label: 'Vision' },
    { id: 'vestibular', label: 'Vestibular' },
    { id: 'proprioception', label: 'Proprioception' },
    { id: 'body', label: 'Body' },
    { id: 'ambient', label: 'Ambient' },
  ],
  SIGNALS: [
    { id: 'physical', label: 'Physical' },
    { id: 'internal', label: 'Internal' },
    { id: 'emitted', label: 'Emitted' },
    { id: 'received', label: 'Received' },
  ],
  INTERVENTION: [
    { id: 'agent', label: 'Controlled Agent' },
    { id: 'movement', label: 'Movement' },
    { id: 'fields', label: 'Fields' },
    { id: 'interaction', label: 'Interaction' },
    { id: 'camera', label: 'Camera' },
  ],
  OBSERVE: [
    { id: 'agent', label: 'Agent' },
    { id: 'body', label: 'Body' },
    { id: 'environment', label: 'Environment' },
    { id: 'cognition', label: 'Cognition' },
    { id: 'predictive', label: 'Predictive State' },
  ],
  RUNS: [{ id: 'catalog', label: 'Catalog' }],
  WORLD_STATUS: [{ id: 'status', label: 'Status' }],
  BODY: [{ id: 'body', label: 'Body' }],
  COGNITION: [{ id: 'cognition', label: 'Cognition' }],
  PREDICTIVE: [{ id: 'predictive', label: 'Predictive' }],
  MECHANISMS: [{ id: 'ablations', label: 'Ablations' }],
  EXPERIMENTER: [{ id: 'agent', label: 'Controlled Agent' }],
  WORLD: [{ id: 'status', label: 'Status' }],
};

const DEFAULT_TAB: Record<string, string> = {
  EXPERIMENT: 'world',
  SENSORS: 'vision',
  SIGNALS: 'physical',
  INTERVENTION: 'agent',
  OBSERVE: 'agent',
  RUNS: 'catalog',
  WORLD_STATUS: 'status',
  BODY: 'body',
  COGNITION: 'cognition',
  PREDICTIVE: 'predictive',
  MECHANISMS: 'ablations',
  EXPERIMENTER: 'agent',
  WORLD: 'status',
};

const SECTION_TITLE: Record<string, string> = {
  EXPERIMENT: 'EXPERIMENT',
  INTERVENTION: 'INTERVENTION',
  OBSERVE: 'OBSERVE',
  SENSORS: 'SENSORS',
  SIGNALS: 'SIGNALS',
  RUNS: 'RUNS',
  WORLD_STATUS: 'WORLD STATUS',
  BODY: 'SENSORS',
  COGNITION: 'OBSERVE',
  PREDICTIVE: 'EXPERIMENT',
  MECHANISMS: 'EXPERIMENT',
  EXPERIMENTER: 'INTERVENTION',
  WORLD: 'WORLD STATUS',
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
  mechanisms: any[];
  onToggleMechanism: (id: string, enabled: boolean) => void;
  onSetVisionRadius?: (radius: number) => void;
  onSetSurfaceDiscrimination?: (mode: 'OFF' | 'LOW' | 'RICH') => void;
  onSetOpticalMapping?: (mode: 'INDEPENDENT' | 'CORRELATED' | 'SHUFFLED' | 'UNIFORM') => void;
  onSetSpatialVision?: (mode: 'LEGACY' | 'ANGULAR' | 'OCCLUSION' | 'TEMPORAL_SPATIAL') => void;
  expPressed?: string | null;
  extras?: Extras;
  onSectionTab?: (inspector: InspectorId, tab: string) => void;
  experimentApplyBar?: ReactNode;
  experimentMechanismDraft?: Record<string, boolean>;
};

function num(v: any, d = 3) {
  return Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—';
}

function BodyMetrics({ physical, body, frame }: { physical: any; body: any; frame: any }) {
  return (
    <InspectorAccordion id="body-metrics" title="Body state">
      <ReadOnlyMetric name="x,y" value={`${num(body.x)} , ${num(body.y)}`} kind="GT" />
      <ReadOnlyMetric name="vx,vy" value={`${num(body.vx)} , ${num(body.vy)}`} kind="GT" />
      <ReadOnlyMetric name="action" value={physical.selected_action || body.selected_action || '—'} />
      <ReadOnlyMetric name="work reservoir" value={num(physical.resources?.reservoir)} kind="GT" />
      <ReadOnlyMetric name="R_A / R_B" value={`${num(physical.resources?.A)} / ${num(physical.resources?.B)}`} kind="GT" />
      {(frame?.world?.resource_objects || []).length > 0 ? (
        <ReadOnlyMetric
          name="resource objects (researcher-only)"
          value={(frame.world.resource_objects as any[]).map((o: any) => {
            const opt = o.optical_response || {};
            const vis = o.agent_optical_contribution_enabled ? 'agent-optics-on' : 'agent-optics-off';
            const hold = o.holder_body_id ? ` holder=${o.holder_body_id}` : '';
            const props = o.passive_material_properties;
            const passive = props
              ? ` compliance=${Number(props.compliance).toFixed(3)} surface_affinity=${Number(props.surface_affinity).toFixed(3)} derivation=${props.derivation_version || props.derivation} researcher-only not agent-accessible passive — no consequence kernel`
              : '';
            const sgObj = o.size_geometry;
            const sg = sgObj
              ? ` size_geo=${sgObj.clamp_status || sgObj.scope_classification || 'scaled'} profile=${sgObj.profile_version || '—'} raw_r=${sgObj.raw_radius != null ? Number(sgObj.raw_radius).toFixed(3) : '—'} resize=NO`
              : '';
            return `${o.object_id} ${o.physical_state}${hold} coll_r=${Number(o.collision_radius ?? 0.25).toFixed(3)} opt_r=${Number(o.optical_radius || 0).toFixed(2)} vhe=${o.vertical_half_extent != null ? Number(o.vertical_half_extent).toFixed(3) : '—'} qty=${Number(o.quantity || 0).toFixed(3)} mass=${Number(o.mass || 0).toFixed(3)}${sg} ${vis} c0=${Number(opt.c0 ?? 0).toFixed(2)}${passive}`;
          }).join(' | ')}
          kind="GT"
        />
      ) : null}
      <MotionCausalInspector whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
      <WhyDidItsShapeChange whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
      <WhyDidItRotate whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
    </InspectorAccordion>
  );
}

export const InspectorDock = memo(function InspectorDock({
  mechanisms, onToggleMechanism, onSetVisionRadius, onSetSurfaceDiscrimination, onSetOpticalMapping, onSetSpatialVision, expPressed, extras,
  onSectionTab, experimentApplyBar, experimentMechanismDraft,
}: Props) {
  void onSetVisionRadius;
  void onSetSurfaceDiscrimination;
  void onSetOpticalMapping;
  void onSetSpatialVision;
  noteRender('InspectorDock');
  const frame = useFrameStore();
  const status = useStatusStore();
  const ws = useWorkspaceStore();
  const ui = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  if (!ws.inspectorOpen) return null;

  const inspector = ws.inspector;
  const tabs = SECTION_TABS[inspector] || SECTION_TABS.SENSORS;
  const activeTab = ui.tabs[inspector] || DEFAULT_TAB[inspector] || tabs[0]?.id;
  const setTab = (id: string) => {
    inspectorUiStore.set({
      ...inspectorUiStore.get(),
      tabs: { ...inspectorUiStore.get().tabs, [inspector]: id },
    });
    onSectionTab?.(inspector, id);
  };

  const physical = frame?.physical || {};
  const body = frame?.body || {};
  const header = frame?.header || {};
  const experimentInspector = inspector === 'EXPERIMENT' || inspector === 'MECHANISMS' || inspector === 'PREDICTIVE';
  /** Global Apply only on Review / Apply — never inside Vision/World/Model category panels. */
  const showGlobalApply = inspector === 'EXPERIMENT' && activeTab === 'review';
  const displayedMechanisms = (experimentInspector && experimentMechanismDraft
    ? overlayMechanismEnabled(mechanisms || [], experimentMechanismDraft)
    : (mechanisms || [])
  ).filter((m: any) => m?.model_line !== 'ACANTHOSTEGA' || String(header.model_line || '') === 'ACANTHOSTEGA');
  const pscOn = Boolean((displayedMechanisms || []).find((m: any) => m.id === 'prospective_scenario_competition')?.enabled);
  const agentLabel = String(status.selectedAgentId || header.selected_agent_id || 'agent_0').toUpperCase();
  const runStatus = String(status.status || header.status || 'UNKNOWN');

  const toggleMechObj = (m: any) => {
    if (!m) return;
    onToggleMechanism(m.id, !m.enabled);
  };

  const cognitionBody = (
    <>
      <ActionDecisionInspector why={frame?.causal_chain?.decision || frame?.mind?.why_this_action} />
      <SensorimotorConsequencePanel />
      <HistoricalSensorimotorSelectionPanel />
    </>
  );
  const predictiveBody = (
    <>
      <InspectorAccordion id="psc-mode" title="Predictive / PSC" defaultOpen>
        <div className="subtle">
          Configuration (enabled flags) is distinct from live interpretation (current stack).
          Intention-like remains Observer interpretation — not a cognition variable.
        </div>
        <PscMotorResolutionControl
          pscEnabled={pscOn}
          refreshKey={`${header.tick ?? ''}-${String(pscOn)}`}
        />
        <PscOffTicksControl />
      </InspectorAccordion>
      <ContextualProspectiveControlPanel frame={frame} agentId={header.selected_agent_id} />
      <SignalSensorimotorPanel />
    </>
  );
  const mechanismsBody = (
    <>
      <MechanismPreflightPanel integrity={frame?.mechanism_integrity} />
      <MechanismsPanel data={{ mechanisms: displayedMechanisms }} onToggle={onToggleMechanism} />
    </>
  );

  let bodyContent: ReactNode = null;
  if (inspector === 'SENSORS' || inspector === 'BODY') {
    if (activeTab === 'vestibular' || activeTab === 'proprioception') {
      bodyContent = (
        <VestibularProprioceptionPanel
          physical={physical}
          agentObservation={frame?.agent_observation}
          mechanisms={displayedMechanisms}
          onToggleMechanism={toggleMechObj}
        />
      );
    } else if (activeTab === 'body' || inspector === 'BODY') {
      bodyContent = <BodyMetrics physical={physical} body={body} frame={frame} />;
    } else if (activeTab === 'ambient') {
      bodyContent = (
        <InspectorAccordion id="ambient-gt" title="Illumination / ambient" defaultOpen>
          <ReadOnlyMetric name="Illumination cycle" value={(displayedMechanisms || []).find((m: any) => m.id === 'illumination_cycle')?.enabled ? 'ON' : 'OFF'} kind="LIVE" />
          <ReadOnlyMetric name="Illumination" value={physical?.near_field_exteroception?.illumination} kind="GT" />
          <div className="subtle">Observer ground truth — not an agent-accessible map.</div>
        </InspectorAccordion>
      );
    } else {
      bodyContent = (
        <>
          <div className="subtle">Vision configuration: Experiment → Vision. This tab is diagnostic.</div>
          <NearFieldSensorPanel
            physical={physical}
            agentObservation={frame?.agent_observation}
            mechanisms={displayedMechanisms}
            onToggleMechanism={toggleMechObj}
          />
          <FovOverlayControls
            agentIds={Object.keys(frame?.agents_views || {}).length
              ? Object.keys(frame.agents_views)
              : (frame?.agents_observer || []).map((a: any) => String(a.observer_id || a.agent_id)).filter(Boolean)}
          />
          {extras?.sensors}
        </>
      );
    }
  } else if (inspector === 'SIGNALS') {
    bodyContent = (
      <>
        {extras?.signals}
        <OscillatorySignalingPanel
          physical={physical}
          agentObservation={frame?.agent_observation}
          mechanisms={displayedMechanisms}
          onToggleMechanism={toggleMechObj}
        />
        {(activeTab === 'internal' || activeTab === 'physical') && <SignalSensorimotorPanel />}
        <div className="subtle">Physical signal coupling is not communication.</div>
      </>
    );
  } else if (inspector === 'EXPERIMENT') {
    bodyContent = extras?.experiment || null;
  } else if (inspector === 'MECHANISMS' || inspector === 'PREDICTIVE') {
    bodyContent = extras?.experiment || (inspector === 'PREDICTIVE' ? predictiveBody : mechanismsBody);
  } else if (inspector === 'INTERVENTION' || inspector === 'EXPERIMENTER') {
    bodyContent = (
      <>
        <div className="subtle" style={{ marginBottom: 8 }}>
          External intervention. Actions are not Tiktaalik cognition. Signals are physical coupling, not messages.
          <SemanticChip kind="INTERVENTION">INTERVENTION</SemanticChip>
        </div>
        <InteractPanel live={frame?.experimenter_interaction} globalPressed={expPressed} layoutTab={activeTab} />
      </>
    );
  } else if (inspector === 'OBSERVE' || inspector === 'COGNITION') {
    const observeTab = inspector === 'COGNITION' ? 'cognition' : activeTab;
    const observeExtra = extras?.observeByTab?.[observeTab];
    if (observeTab === 'body') {
      bodyContent = (
        <>
          <BodyMetrics physical={physical} body={body} frame={frame} />
          {observeExtra}
        </>
      );
    } else if (observeTab === 'cognition') {
      bodyContent = (
        <>
          {cognitionBody}
          {observeExtra}
        </>
      );
    } else if (observeTab === 'predictive') {
      bodyContent = (
        <>
          {predictiveBody}
          {observeExtra}
        </>
      );
    } else {
      bodyContent = observeExtra || <div className="subtle">No Observer slice for this tab.</div>;
    }
  } else if (inspector === 'RUNS') {
    bodyContent = extras?.runs || <div className="subtle">No run catalog loaded.</div>;
  } else if (inspector === 'WORLD_STATUS' || inspector === 'WORLD') {
    bodyContent = extras?.worldStatus || mechanismsBody;
  }

  return (
    <aside className="inspector-dock" data-testid="inspector-dock" data-inspector={inspector} data-inspector-tab={activeTab}>
      <header className="inspector-sticky">
        <div className="inspector-sticky-row">
          <strong>{SECTION_TITLE[inspector] || inspector}</strong>
          <span className="subtle">{agentLabel}</span>
          <SemanticChip kind={runStatus === 'RUNNING' ? 'LIVE' : 'STATUS'}>{runStatus}</SemanticChip>
          {inspector === 'INTERVENTION' || inspector === 'EXPERIMENTER' ? (
            <SemanticChip kind="INTERVENTION">INTERVENTION</SemanticChip>
          ) : inspector === 'OBSERVE' || inspector === 'COGNITION' ? (
            <SemanticChip kind="OBSERVER">OBSERVER</SemanticChip>
          ) : inspector === 'EXPERIMENT' || inspector === 'MECHANISMS' || inspector === 'PREDICTIVE' ? (
            <SemanticChip kind="STATUS">PREPARE RUN</SemanticChip>
          ) : null}
        </div>
        <InspectorTabs tabs={tabs} active={activeTab} onChange={setTab} />
      </header>
      <div className="inspector-body">
        {bodyContent}
      </div>
      {showGlobalApply && experimentApplyBar ? (
        <footer className="inspector-apply-bar" data-testid="experiment-apply-bar">
          {experimentApplyBar}
        </footer>
      ) : experimentInspector && activeTab !== 'review' ? (
        <footer className="inspector-apply-bar inspector-apply-hint" data-testid="experiment-apply-hint">
          <span className="subtle">
            Draft edits only — current run unchanged. Use Experiment → Review / Apply to apply configuration and start a new run at tick 0.
          </span>
        </footer>
      ) : null}
    </aside>
  );
});
