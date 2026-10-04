/** S7C Destination-depth — Organism owns center with phenomenon-first state.

Uses only existing frame authorities. No invented anatomy/health/emotion.
Display-only agent selection preserves tick.
*/

import { PhenomenonDetails } from '../components/PhenomenonDetails';

type Props = {
  frame: any;
  selectedAgentId: string;
  agentCount: number;
  onSelectAgent: (index: number) => void;
};

function agentRow(frame: any, id: string): any {
  const list = frame?.agents_observer || [];
  return list.find((a: any) => String(a.observer_id || a.agent_id) === id) || null;
}

function fmt(n: unknown, digits = 2): string {
  const v = Number(n);
  return Number.isFinite(v) ? v.toFixed(digits) : '—';
}

export function OrganismCentralWorkspace({
  frame,
  selectedAgentId,
  agentCount,
  onSelectAgent,
}: Props) {
  const header = frame?.header || {};
  const physical = frame?.physical || {};
  const body = frame?.body || {};
  const world = frame?.world || {};
  const a = agentRow(frame, selectedAgentId);
  const tick = header.tick ?? '—';
  const gen = header.runtime_generation ?? '—';
  const action = a?.selected_action
    || physical.selected_action
    || header.selected_action
    || '—';
  const motorSrc = a?.selection_source || physical.motor?.selection_source || '—';
  const support = world.last_free_space_support_state?.support_state
    || world.free_space_state?.support_state
    || a?.support_state
    || '—';
  const contact = physical.body_contact?.status
    || world.body_object_contact?.status
    || '—';
  const held = world.held_resource_summary
    || physical.manipulators?.held
    || physical.grasp?.held
    || null;
  const vision = physical.near_field_exteroception || {};
  const visionOn = vision.enabled === true || vision.perception_enabled === true;
  const n = Math.max(1, agentCount);
  const available = Boolean(a || physical.selected_action != null || body);

  const categories = [
    {
      id: 'body',
      title: 'Body and support',
      summary: `support=${String(support)} · contact=${String(contact)}`,
      children: (
        <div className="subtle">
          <div>support_state = {String(support)}</div>
          <div>contact = {String(contact)}</div>
          <div>pos = ({fmt(a?.x ?? body.x)}, {fmt(a?.y ?? body.y)})</div>
          <div>orientation fields shown only when present on runtime payload.</div>
        </div>
      ),
    },
    {
      id: 'held',
      title: 'Manipulators and held object',
      summary: held ? 'held object present in authority' : 'no held-object summary in frame',
      children: (
        <div className="subtle">
          {held ? (
            <pre className="phenomenon-pre">{JSON.stringify(held, null, 2).slice(0, 1200)}</pre>
          ) : (
            <div>No held-object authority on this frame. Not invented.</div>
          )}
        </div>
      ),
    },
    {
      id: 'motor',
      title: 'Current motor output',
      summary: `${String(action)} · ${String(motorSrc)}`,
      children: (
        <div className="subtle">
          <div>selected_action = {String(action)}</div>
          <div>selection_source = {String(motorSrc)}</div>
          <div>selection_reason = {String(a?.selection_reason || '—')}</div>
          <div>WAIT/MOVE counts = {String(a?.wait_count ?? '—')} / {String(a?.move_count ?? '—')}</div>
        </div>
      ),
    },
    {
      id: 'contacts',
      title: 'Physical contacts and consequences',
      summary: 'existing contact / work receipts only',
      children: (
        <div className="subtle">
          <div>collision_count = {String(a?.collision_count ?? '—')}</div>
          <div>distance_travelled = {fmt(a?.distance_travelled, 3)}</div>
          <div>unique_cells = {String(a?.unique_cells_visited ?? '—')}</div>
          <div>Compact consequence from agents_observer — not a narrative.</div>
        </div>
      ),
    },
    {
      id: 'sensory',
      title: 'Available sensory boundaries',
      summary: visionOn ? 'near-field vision authority ON' : 'vision OFF / unavailable',
      children: (
        <div className="subtle">
          <div>vision enabled = {String(visionOn)}</div>
          <div>spatial_vision = {String(vision.spatial_vision || '—')}</div>
          <div>radius = {String(vision.radius ?? vision.configured_radius ?? '—')}</div>
          <div>FPV / Hearing destinations own full sensory reconstructions.</div>
        </div>
      ),
    },
    {
      id: 'cognition',
      title: 'Cognition-facing state',
      summary: 'values already on agents_observer / mind projection',
      children: (
        <div className="subtle">
          <div>supported_actions = {(a?.supported_actions || []).join(', ') || '—'}</div>
          <div>prospections = {String(a?.prospective_compositions ?? '—')}</div>
          <div>No restoration of discarded sensory detail.</div>
        </div>
      ),
    },
    {
      id: 'receipts',
      title: 'Recent causal receipts',
      summary: 'open Events / causal chain for full stream',
      children: (
        <div className="subtle">
          Causal chain and structured events remain on Events / Observe inspectors.
          This category does not invent narratives.
        </div>
      ),
    },
    {
      id: 'authority',
      title: 'Scientific authority and limitations',
      summary: 'not consciousness · not health · not taxon biology',
      children: (
        <div className="subtle">
          <div>selected_agent_id = {String(selectedAgentId)}</div>
          <div>runtime_generation = {String(gen)}</div>
          <div>public_preset = {String(header.public_preset || frame?.experiment?.runtime?.public_preset || '—')}</div>
          <div><strong>NOT</strong> anatomy inventory · <strong>NOT</strong> health/energy/motivation · <strong>NOT</strong> emotion · <strong>NOT</strong> conscious experience.</div>
          <div>Missing fields render as UNAVAILABLE / — — never fabricated.</div>
        </div>
      ),
    },
  ];

  return (
    <div
      className="organism-central-workspace"
      data-testid="organism-central-workspace"
      data-owns-center="true"
      aria-label="Organism observation"
    >
      <header className="fpv-central-header" data-testid="organism-central-header">
        <div className="fpv-central-agents" role="group" aria-label="Selected organism">
          {Array.from({ length: n }, (_, i) => (
            <button
              key={i}
              type="button"
              className={selectedAgentId === `agent_${i}` ? 'active' : ''}
              data-testid={`organism-select-agent-${i}`}
              onClick={() => onSelectAgent(i)}
            >
              AGENT {i}
            </button>
          ))}
        </div>
        <div className="fpv-central-status">
          <span data-testid="organism-live-state">{available ? 'LIVE' : 'UNAVAILABLE'}</span>
          <span className="subtle">tick={String(tick)} · gen={String(gen)}</span>
          <span className="subtle">action=<strong>{String(action)}</strong></span>
          <span className="subtle">support={String(support)}</span>
        </div>
      </header>

      <div className="organism-central-primary" data-testid="organism-central-primary">
        <div className="organism-state-card panel">
          <h2 className="organism-state-title">{String(selectedAgentId).toUpperCase()}</h2>
          <div className="organism-state-grid">
            <div><span className="subtle">Position</span><strong>({fmt(a?.x ?? body.x)}, {fmt(a?.y ?? body.y)})</strong></div>
            <div><span className="subtle">Action</span><strong>{String(action)}</strong></div>
            <div><span className="subtle">Support</span><strong>{String(support)}</strong></div>
            <div><span className="subtle">Contact</span><strong>{String(contact)}</strong></div>
            <div><span className="subtle">Vision</span><strong>{visionOn ? 'ON' : 'OFF'}</strong></div>
            <div><span className="subtle">Held</span><strong>{held ? 'PRESENT' : 'NONE / —'}</strong></div>
          </div>
          <p className="subtle">Observable organism state from runtime authorities — not a biological organism portrait.</p>
        </div>
      </div>

      <PhenomenonDetails categories={categories} testIdPrefix="organism" />
    </div>
  );
}
