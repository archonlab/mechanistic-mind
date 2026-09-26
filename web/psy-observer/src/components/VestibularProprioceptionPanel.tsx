/** Observer Sensors — Vestibular / Proprioception (WORLD GT vs AGENT-ACCESSIBLE). */

type Props = {
  physical?: any;
  agentObservation?: Record<string, number> | null;
  mechanisms?: any[];
  onToggleMechanism?: (m: any) => void;
  cognitionEnabled?: boolean;
};

function KV({ name, value }: { name: string; value: any }) {
  const missing = value === undefined || value === null || value === '';
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>{missing ? 'NOT AVAILABLE' : String(value)}</strong>
    </div>
  );
}

function fmt(v: any, digits = 4) {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return null;
  return Number(v).toFixed(digits);
}

export function VestibularProprioceptionPanel({
  physical,
  agentObservation,
  mechanisms,
  onToggleMechanism,
  cognitionEnabled = true,
}: Props) {
  const vest = physical?.vestibular;
  const prop = physical?.neck_proprioception;
  const orient = physical?.orientation;
  const cogn = agentObservation || {};
  const vestMech = (mechanisms || []).find((m: any) => m.id === 'physical_vestibular_sensing');
  const propMech = (mechanisms || []).find((m: any) => m.id === 'neck_proprioception');

  const agentVest0 = cognitionEnabled ? cogn.vest_0 : undefined;
  const agentVest1 = cognitionEnabled ? cogn.vest_1 : undefined;
  const agentProp0 = cognitionEnabled ? cogn.prop_neck_0 : undefined;
  const agentProp1 = cognitionEnabled ? cogn.prop_neck_1 : undefined;

  return (
    <div className="panel science-card" style={{ marginTop: 12 }}>
      <h3>VESTIBULAR / PROPRIOCEPTION</h3>
      <div className="subtle">
        Physical body-local rotational sensing · not compass · not self-motion labels · not gaze
      </div>

      <div className="section-label" style={{ marginTop: 8 }}>Mechanism (LIVE)</div>
      {vestMech ? (
        <div className="metric" style={{ alignItems: 'center' }}>
          <span>Physical vestibular sensing</span>
          <button type="button" disabled={!onToggleMechanism} title={!onToggleMechanism ? 'Control not wired' : 'LIVE mutable'} onClick={() => onToggleMechanism?.(vestMech)}>
            {vestMech.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      ) : (
        <div className="na">Vestibular mechanism not in registry</div>
      )}
      {propMech ? (
        <div className="metric" style={{ alignItems: 'center' }}>
          <span>Neck proprioception</span>
          <button type="button" disabled={!onToggleMechanism} title={!onToggleMechanism ? 'Control not wired' : 'LIVE mutable'} onClick={() => onToggleMechanism?.(propMech)}>
            {propMech.enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      ) : (
        <div className="na">Neck proprioception mechanism not in registry</div>
      )}

      <div className="section-label" style={{ marginTop: 10 }}>A. WORLD / BODY GROUND TRUTH</div>
      <KV name="Body heading θ" value={fmt(vest?.WORLD_GT?.body_theta ?? orient?.theta)} />
      <KV name="Body ω" value={fmt(vest?.WORLD_GT?.body_omega ?? orient?.omega)} />
      <KV name="Body α" value={fmt(vest?.WORLD_GT?.body_alpha ?? orient?.receipt?.alpha)} />
      <KV name="Head relative angle" value={fmt(prop?.WORLD_GT?.head_relative_angle ?? orient?.head_relative_angle)} />
      <KV name="Head world heading" value={fmt(prop?.WORLD_GT?.head_world_heading ?? orient?.head_world_heading)} />
      <KV name="Head ω" value={fmt(prop?.WORLD_GT?.head_omega ?? orient?.head_omega)} />
      <KV name="Neck motor" value={fmt(prop?.WORLD_GT?.neck_motor ?? orient?.neck_motor)} />

      <div className="section-label" style={{ marginTop: 10 }}>B. AGENT-ACCESSIBLE SENSOR STATE</div>
      {!cognitionEnabled ? (
        <div className="na">Cognition / sensor path NOT AVAILABLE for this body (e.g. Undercover)</div>
      ) : null}
      <KV name="vest_0" value={fmt(agentVest0 ?? vest?.AGENT_ACCESSIBLE?.vest_0)} />
      <KV name="vest_1" value={fmt(agentVest1 ?? vest?.AGENT_ACCESSIBLE?.vest_1)} />
      <KV
        name="vestibular status"
        value={vest?.AGENT_ACCESSIBLE?.status || (vestMech?.enabled ? 'AVAILABLE' : 'NOT_AVAILABLE')}
      />
      <KV name="prop_neck_0" value={fmt(agentProp0 ?? prop?.AGENT_ACCESSIBLE?.prop_neck_0)} />
      <KV name="prop_neck_1" value={fmt(agentProp1 ?? prop?.AGENT_ACCESSIBLE?.prop_neck_1)} />
      <KV
        name="proprioception status"
        value={prop?.AGENT_ACCESSIBLE?.status || (propMech?.enabled ? 'AVAILABLE' : 'NOT_AVAILABLE')}
      />
      <div className="subtle" style={{ marginTop: 6 }}>
        Anonymous numeric channels only. Observer knows physical provenance; cognition does not
        receive heading / compass / target direction.
      </div>
    </div>
  );
}
