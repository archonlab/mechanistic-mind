/** S7C Destination workspaces barrel — Hearing + re-exports. */

import { useMemo, useState, type ReactNode } from 'react';
import { HearingWorkspacePanel } from '../acoustic/HearingWorkspacePanel.tsx';
import {
  getListeningModeOwner,
  subscribeListeningMode,
} from '../acoustic/listeningModeOwner.ts';
import { PhenomenonDetails } from '../components/PhenomenonDetails';
import { useEffect } from 'react';

export { OrganismCentralWorkspace } from '../destinations/OrganismCentralWorkspace';
export { EventsCentralWorkspace } from '../destinations/EventsCentralWorkspace';
export { SimulationInfoWorkspace } from '../destinations/SimulationInfoWorkspace';
export { ScientificToolsLanding } from '../destinations/ScientificToolsLanding';

type HearingProps = {
  frame: any;
  executionMode?: string;
  paused?: boolean;
  runtimeGeneration?: number | null;
  selectedCell?: any;
};

/**
 * Hearing owns center: receptor phenomenon first; full HearingWorkspacePanel
 * engines remain authoritative (keep-alive when dock suppresses duplicate).
 */
export function HearingObservationWorkspace({
  frame,
  executionMode,
  paused,
  runtimeGeneration,
  selectedCell,
}: HearingProps) {
  const [, bump] = useState(0);
  useEffect(() => subscribeListeningMode(() => bump((n) => n + 1)), []);

  const world = frame?.world;
  const sav = world?.selected_organism_auditory_view;
  const stream = world?.authoritative_physical_acoustic_stream;
  const oatt = world?.organism_auditory_transfert_trace || world?.organism_auditory_boundary_receipt;
  const agent = sav?.selected_agent_id ?? frame?.header?.selected_agent_id ?? '—';
  const latest = sav?.latest || sav;
  const available = Boolean(sav?.available ?? latest);
  const trueZero = Boolean(latest?.true_zero || latest?.true_zero_exact_trace || sav?.true_zero);
  const missing = !available && !trueZero;
  const owner = getListeningModeOwner();
  const obsTick = latest?.observation_tick ?? latest?.tick ?? frame?.header?.tick ?? '—';

  const liveState = missing ? 'UNAVAILABLE' : trueZero ? 'ZERO' : available ? 'LIVE' : 'UNAVAILABLE';

  const categories = useMemo(() => [
    {
      id: 'reached',
      title: 'What reached the receptors',
      summary: `${liveState} · agent=${String(agent)}`,
      children: (
        <div className="subtle">
          <div>selected_organism_auditory_view available = {String(Boolean(sav))}</div>
          <div>true_zero = {String(trueZero)} · missing = {String(missing)}</div>
          <div>observation_tick = {String(obsTick)}</div>
          <div>Missing ≠ silence. True zero is a valid exact frame when asserted by authority.</div>
        </div>
      ),
    },
    {
      id: 'sources',
      title: 'Physical sources and transport',
      summary: stream ? String(stream.schema || 'acoustic stream') : 'no stream payload',
      children: (
        <div className="subtle">
          <div>authoritative_physical_acoustic_stream = {stream ? 'present' : 'absent'}</div>
          <div>Physical field layer ≠ organism receptor layer ≠ researcher playback.</div>
        </div>
      ),
    },
    {
      id: 'channels',
      title: 'Receptor channels',
      summary: 'compact channel status from auditory view',
      children: (
        <div className="subtle">
          Channel numerics remain inside Selected Organism auditory panels below.
          No fake Hz / SPL calibration claims.
        </div>
      ),
    },
    {
      id: 'cognition',
      title: 'Cognition boundary',
      summary: 'cognition-facing auditory values only when present',
      children: (
        <div className="subtle">
          Cognition-facing fold cannot restore discarded receptor detail.
          Researcher sonification is not organism hearing.
        </div>
      ),
    },
    {
      id: 'timing',
      title: 'LPS and OATT timing',
      summary: 'LPS transport delay ≠ OATT A3→A5 alignment',
      children: (
        <div className="subtle" data-testid="hearing-timing-detail">
          <div>LPS transport timing remains distinct from OATT alignment.</div>
          <div>oatt/boundary payload = {oatt ? 'present' : 'absent'}</div>
          <div>observation_tick = {String(obsTick)}</div>
        </div>
      ),
    },
    {
      id: 'playback',
      title: 'Researcher playback/sonification',
      summary: `listening owner=${owner}`,
      children: (
        <div className="subtle">
          Listening mode / mute / C1 / SAV2 controls are researcher Class A UI.
          They do not reset the simulation and are not original organism hearing.
        </div>
      ),
    },
    {
      id: 'receipts',
      title: 'Causal receipts',
      summary: 'see Events for bounded stream',
      children: (
        <div className="subtle">Acoustic causal receipts appear in the Events stream when present.</div>
      ),
    },
    {
      id: 'authority',
      title: 'Scientific authority and limitations',
      summary: 'no semantic communication · no fake Hz/SPL',
      children: (
        <div className="subtle">
          <div>auditory_view schema = {String(sav?.schema || '—')}</div>
          <div>stream schema = {String(stream?.schema || '—')}</div>
          <div><strong>NOT</strong> original organism hearing audio · <strong>NOT</strong> semantic communication.</div>
        </div>
      ),
    },
  ], [agent, available, liveState, missing, oatt, obsTick, owner, sav, stream, trueZero]);

  return (
    <div
      className="hearing-central-workspace"
      data-testid="hearing-central-workspace"
      data-owns-center="true"
      data-live-state={liveState}
      aria-label="Hearing observation"
    >
      <header className="fpv-central-header" data-testid="hearing-central-header">
        <strong>HEARING</strong>
        <span data-testid="hearing-live-state">{liveState}</span>
        <span className="subtle">
          agent={String(agent).toUpperCase()} · obs_tick={String(obsTick)} · owner={owner}
        </span>
        <span className="subtle">Receptor phenomenon first · playback separate</span>
      </header>

      <div className="hearing-central-primary" data-testid="hearing-central-primary">
        <div className="panel hearing-phenomenon-card" data-testid="hearing-phenomenon-card">
          <div className="organism-state-grid">
            <div><span className="subtle">Receptor view</span><strong>{available || trueZero ? 'AUTHORITY PRESENT' : 'UNAVAILABLE'}</strong></div>
            <div><span className="subtle">True zero</span><strong>{String(trueZero)}</strong></div>
            <div><span className="subtle">Missing</span><strong>{String(missing)}</strong></div>
            <div><span className="subtle">Listening</span><strong>{owner}</strong></div>
          </div>
          <p className="subtle">
            Layers: (1) physical acoustic field · (2) selected-organism receptor · (3) cognition-facing values · (4) researcher sonification.
          </p>
        </div>
        <HearingWorkspacePanel
          frame={frame}
          executionMode={String(executionMode || 'LIVE')}
          paused={!!paused}
          runtimeGeneration={runtimeGeneration != null ? Number(runtimeGeneration) : null}
          selectedCell={selectedCell}
        />
      </div>

      <PhenomenonDetails categories={categories} testIdPrefix="hearing" />
    </div>
  );
}

/** @deprecated thin wrappers kept for import compatibility — prefer destination modules. */
export function OrganismObservationWorkspace(props: {
  selectedAgentId: string;
  tick: number | string;
  generation: number | string;
  primary: ReactNode;
  details?: ReactNode;
}) {
  return (
    <div className="organism-central-workspace" data-testid="organism-central-workspace" data-owns-center="true">
      <header className="fpv-central-header">
        <strong>ORGANISM</strong>
        <span className="subtle">
          {String(props.selectedAgentId).toUpperCase()} · tick={String(props.tick)} · gen={String(props.generation)}
        </span>
      </header>
      <div className="organism-central-primary">{props.primary}</div>
      {props.details ? (
        <PhenomenonDetails
          categories={[{ id: 'mechanisms', title: 'Detail categories', summary: 'legacy', children: props.details }]}
          testIdPrefix="organism"
        />
      ) : null}
    </div>
  );
}

export function EventsObservationWorkspace(props: { primary: ReactNode; filters?: ReactNode }) {
  return (
    <div className="events-central-workspace" data-testid="events-central-workspace" data-owns-center="true">
      <header className="fpv-central-header"><strong>EVENTS</strong></header>
      <div className="events-central-primary">{props.primary}</div>
      {props.filters ? (
        <PhenomenonDetails
          categories={[{ id: 'filters', title: 'Filters', summary: '', children: props.filters }]}
          testIdPrefix="events"
        />
      ) : null}
    </div>
  );
}
