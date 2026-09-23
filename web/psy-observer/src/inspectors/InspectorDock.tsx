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
import { SensorimotorConsequencePanel } from '../components/SensorimotorConsequencePanel';
import { SignalSensorimotorPanel } from '../components/SignalSensorimotorPanel';
import { VestibularProprioceptionPanel } from '../components/VestibularProprioceptionPanel';
import { VisionExperimenterControl, visionRowFromIntegrity } from '../components/VisionExperimenterControl';
import { WhyDidItRotate } from '../components/WhyDidItRotate';
import { WhyDidItsShapeChange } from '../components/WhyDidItsShapeChange';
import {
  inspectorUiStore,
  noteRender,
  type InspectorId,
} from '../observer/stores';
import { useFrameStore, useStatusStore, useWorkspaceStore } from '../observer/useExternalStore';
import { InspectorAccordion, InspectorTabs, ReadOnlyMetric, SemanticChip } from './primitives';
import { FovOverlayControls } from './FovOverlayControls';

export const SECTION_TABS: Record<string, { id: string; label: string }[]> = {
  EXPERIMENT: [
    { id: 'ecology', label: 'Ecology' },
    { id: 'perception', label: 'Perception' },
    { id: 'body', label: 'Body' },
    { id: 'cognition', label: 'Cognition' },
    { id: 'predictive', label: 'Predictive' },
    { id: 'ablations', label: 'Ablations' },
    { id: 'world', label: 'World' },
    { id: 'model', label: 'Model' },
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
  EXPERIMENT: 'ecology',
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
  expPressed?: string | null;
  extras?: Extras;
  onSectionTab?: (inspector: InspectorId, tab: string) => void;
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
      <MotionCausalInspector whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
      <WhyDidItsShapeChange whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
      <WhyDidItRotate whyMove={frame?.causal_chain?.why_did_it_move} physical={physical} />
    </InspectorAccordion>
  );
}

export const InspectorDock = memo(function InspectorDock({
  mechanisms, onToggleMechanism, onSetVisionRadius, expPressed, extras,
  onSectionTab,
}: Props) {
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
  const pscOn = Boolean((mechanisms || []).find((m: any) => m.id === 'prospective_scenario_competition')?.enabled);
  const visionMech = (mechanisms || []).find((m: any) => m.id === 'physical_near_field_vision');
  const visionMechOn = Boolean(visionMech?.enabled);
  const agentLabel = String(status.selectedAgentId || header.selected_agent_id || 'agent_0').toUpperCase();
  const runStatus = String(status.status || header.status || 'UNKNOWN');
  const vRow = visionRowFromIntegrity(frame?.mechanism_integrity);
  const runtimeR = Number(
    physical?.near_field_exteroception?.vision_radius
    ?? physical?.near_field_exteroception?.radius
    ?? vRow?.runtime_radius
    ?? 1,
  );
  const configuredR = vRow?.configured_radius != null ? Number(vRow.configured_radius) : runtimeR;

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
      </InspectorAccordion>
      <ContextualProspectiveControlPanel frame={frame} agentId={header.selected_agent_id} />
      <SignalSensorimotorPanel />
    </>
  );
  const mechanismsBody = (
    <>
      <MechanismPreflightPanel integrity={frame?.mechanism_integrity} />
      <MechanismsPanel data={{ mechanisms }} onToggle={onToggleMechanism} />
    </>
  );

  let bodyContent: ReactNode = null;
  if (inspector === 'SENSORS' || inspector === 'BODY') {
    if (activeTab === 'vestibular' || activeTab === 'proprioception') {
      bodyContent = (
        <VestibularProprioceptionPanel
          physical={physical}
          agentObservation={frame?.agent_observation}
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechObj}
        />
      );
    } else if (activeTab === 'body' || inspector === 'BODY') {
      bodyContent = <BodyMetrics physical={physical} body={body} frame={frame} />;
    } else if (activeTab === 'ambient') {
      bodyContent = (
        <InspectorAccordion id="ambient-gt" title="Illumination / ambient" defaultOpen>
          <ReadOnlyMetric name="Illumination cycle" value={(mechanisms || []).find((m: any) => m.id === 'illumination_cycle')?.enabled ? 'ON' : 'OFF'} kind="LIVE" />
          <ReadOnlyMetric name="Illumination" value={physical?.near_field_exteroception?.illumination} kind="GT" />
          <div className="subtle">Observer ground truth — not an agent-accessible map.</div>
        </InspectorAccordion>
      );
    } else {
      bodyContent = (
        <>
          <VisionExperimenterControl
            visionEnabled={visionMechOn}
            runtimeRadius={runtimeR}
            configuredRadius={configuredR}
            mismatch={Boolean(vRow?.status && vRow.status !== 'READY')}
            visionMechanismPresent={!!visionMech || !!vRow}
            onToggleVision={visionMech ? () => toggleMechObj(visionMech) : undefined}
            onSetRadius={onSetVisionRadius}
          />
          <NearFieldSensorPanel
            physical={physical}
            agentObservation={frame?.agent_observation}
            mechanisms={mechanisms}
            onToggleMechanism={toggleMechObj}
            onSetVisionRadius={onSetVisionRadius}
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
          mechanisms={mechanisms}
          onToggleMechanism={toggleMechObj}
        />
        {(activeTab === 'internal' || activeTab === 'physical') && <SignalSensorimotorPanel />}
        <div className="subtle">Physical signal coupling is not communication.</div>
      </>
    );
  } else if (inspector === 'EXPERIMENT' || inspector === 'MECHANISMS' || inspector === 'PREDICTIVE') {
    bodyContent = (
      <>
        {extras?.experiment}
        {inspector === 'PREDICTIVE' && predictiveBody}
        {(activeTab === 'ablations' || inspector === 'MECHANISMS') && mechanismsBody}
        {activeTab === 'cognition' && cognitionBody}
      </>
    );
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
            <SemanticChip kind="LIVE">LIVE / PRE-RUN</SemanticChip>
          ) : null}
        </div>
        <InspectorTabs tabs={tabs} active={activeTab} onChange={setTab} />
      </header>
      <div className="inspector-body">
        {bodyContent}
      </div>
    </aside>
  );
});
