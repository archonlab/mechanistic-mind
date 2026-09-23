/**
 * Observe V2 — CURRENT STATE extraction from a live Observer frame.
 * Presentation only. Reuses motor_control / physical / observation authorities.
 */

export type NaValue = number | string | boolean | null | undefined;

export function na(v: NaValue, fallback: string | number = 'NOT AVAILABLE'): string | number {
  if (v === null || v === undefined) return fallback;
  if (typeof v === 'number' && Number.isNaN(v)) return fallback;
  if (typeof v === 'string' && (v === '' || v === 'undefined')) return fallback;
  return v as string | number;
}

export type ObserveProvenance = {
  run_id: string;
  generation: string | number;
  tick: string | number;
  agent_id: string;
  motor_schema: string;
  telemetry_schema: string;
  status: string;
};

export type MotorOutputView = {
  schema: string;
  locomotion: string;
  neck: string;
  osc_freq_delta: number | 'NOT AVAILABLE';
  osc_amp_delta: number | 'NOT AVAILABLE';
  osc_emit_trigger: boolean | 'NOT AVAILABLE';
  push: string;
  legacy_action: string | 'NOT AVAILABLE';
  summary_line: string;
};

export type ActiveEffectorsView = {
  motion_active: boolean;
  speed: number | 'NOT AVAILABLE';
  vx: number | 'NOT AVAILABLE';
  vy: number | 'NOT AVAILABLE';
  head_relative_angle: number | 'NOT AVAILABLE';
  head_world_heading: number | 'NOT AVAILABLE';
  head_omega: number | 'NOT AVAILABLE';
  neck_torque: string | number | 'NOT AVAILABLE';
  osc_emitting: boolean;
  osc_freq_u: number | 'NOT AVAILABLE';
  osc_amp_u: number | 'NOT AVAILABLE';
  osc_remaining: number | 'NOT AVAILABLE';
  push_active: boolean;
  push_exertion: number | 'NOT AVAILABLE';
  contact_active: boolean | 'NOT AVAILABLE';
};

export type PassiveInputView = {
  vision_enabled: boolean;
  exo_0: number | 'NOT AVAILABLE';
  exo_1: number | 'NOT AVAILABLE';
  exo_2: number | 'NOT AVAILABLE';
  vision_radius: number | 'NOT AVAILABLE';
  osc_l: number[];
  osc_r: number[];
  osc_rx_active: boolean;
  field_a: number | 'NOT AVAILABLE';
  field_b: number | 'NOT AVAILABLE';
  legacy_fields_present: boolean;
  vest_0: number | 'NOT AVAILABLE';
  vest_1: number | 'NOT AVAILABLE';
  prop_neck_0: number | 'NOT AVAILABLE';
  prop_neck_1: number | 'NOT AVAILABLE';
  emitting: boolean;
  receiving: boolean;
  observer_gt_rx_provenance: string | 'NOT AVAILABLE';
};

export type ObserveCurrentState = {
  provenance: ObserveProvenance;
  motor: MotorOutputView;
  effectors: ActiveEffectorsView;
  passive: PassiveInputView;
};

function bandSeries(obs: Record<string, any> | null | undefined, prefix: string, n = 6): number[] {
  if (!obs) return [];
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const k = `${prefix}${i}`;
    if (k in obs && obs[k] != null && Number.isFinite(Number(obs[k]))) {
      out.push(Number(obs[k]));
    }
  }
  // Also accept AGENT_ACCESSIBLE channel map
  if (!out.length) {
    for (let i = 0; i < n; i++) {
      const k = `${prefix}${i}`;
      if (obs[k] != null && Number.isFinite(Number(obs[k]))) out.push(Number(obs[k]));
    }
  }
  return out;
}

function spark(vals: number[]): string {
  if (!vals.length) return '—';
  const blocks = '▁▂▃▄▅▆▇█';
  const max = Math.max(...vals.map((v) => Math.abs(v)), 1e-12);
  return vals
    .map((v) => {
      const idx = Math.max(0, Math.min(7, Math.round((Math.abs(v) / max) * 7)));
      return blocks[idx];
    })
    .join('');
}

export function bandSpark(vals: number[]): string {
  return spark(vals);
}

export function buildObserveProvenance(frame: any, opts?: {
  run_id?: string | null;
  agent_id?: string | null;
}): ObserveProvenance {
  const header = frame?.header || {};
  const mc = frame?.motor_control || {};
  return {
    run_id: String(opts?.run_id || header.run_id || frame?.run_id || 'NOT AVAILABLE'),
    generation: header.runtime_generation ?? frame?.observation?.runtime_generation ?? 'NOT AVAILABLE',
    tick: header.tick ?? frame?.observation?.ticks?.runtime ?? 'NOT AVAILABLE',
    agent_id: String(
      opts?.agent_id
      || frame?.observer?.selected_agent_id
      || header.selected_agent_id
      || 'agent_0',
    ),
    motor_schema: String(mc.schema || header.motor_schema || 'NOT AVAILABLE'),
    telemetry_schema: String(
      frame?.scientific_history?.telemetry_schema
      || header.telemetry_schema
      || 'NOT AVAILABLE',
    ),
    status: String(header.status || 'UNKNOWN'),
  };
}

export function buildMotorOutputView(frame: any): MotorOutputView {
  const mc = frame?.motor_control;
  const physical = frame?.physical || {};
  if (!mc || !mc.schema) {
    const action = physical.selected_action || frame?.header?.selected_action;
    if (action != null) {
      return {
        schema: 'LEGACY_SINGLE_SLOT',
        locomotion: String(action),
        neck: 'NOT AVAILABLE',
        osc_freq_delta: 'NOT AVAILABLE',
        osc_amp_delta: 'NOT AVAILABLE',
        osc_emit_trigger: 'NOT AVAILABLE',
        push: 'NOT AVAILABLE',
        legacy_action: String(action),
        summary_line: `ACTION: ${action}`,
      };
    }
    return {
      schema: 'NOT AVAILABLE',
      locomotion: 'NOT AVAILABLE',
      neck: 'NOT AVAILABLE',
      osc_freq_delta: 'NOT AVAILABLE',
      osc_amp_delta: 'NOT AVAILABLE',
      osc_emit_trigger: 'NOT AVAILABLE',
      push: 'NOT AVAILABLE',
      legacy_action: 'NOT AVAILABLE',
      summary_line: 'MOTOR: NOT AVAILABLE',
    };
  }
  const schema = String(mc.schema);
  const out = mc.current_motor_output || {};
  if (schema === 'LEGACY_SINGLE_SLOT') {
    const action = String(out.locomotion || out.display || physical.selected_action || 'NOT AVAILABLE');
    return {
      schema,
      locomotion: action,
      neck: 'NOT AVAILABLE',
      osc_freq_delta: 'NOT AVAILABLE',
      osc_amp_delta: 'NOT AVAILABLE',
      osc_emit_trigger: 'NOT AVAILABLE',
      push: 'NOT AVAILABLE',
      legacy_action: action,
      summary_line: `MOTOR SCHEMA: LEGACY_SINGLE_SLOT · ACTION: ${action}`,
    };
  }
  const osc = out.oscillator || {};
  const loco = String(out.locomotion || 'NONE');
  const neck = String(out.neck || 'NONE');
  const emit = Boolean(osc.emit_trigger);
  const push = out.push ? 'ON' : 'OFF';
  const oscLabel = emit
    ? 'EMIT'
    : (Number(osc.freq_delta) || Number(osc.amp_delta))
      ? `Δf=${osc.freq_delta || 0} Δa=${osc.amp_delta || 0}`
      : 'NONE';
  return {
    schema: 'COMPOSITE_MOTOR_V1',
    locomotion: loco,
    neck,
    osc_freq_delta: Number(osc.freq_delta || 0),
    osc_amp_delta: Number(osc.amp_delta || 0),
    osc_emit_trigger: emit,
    push,
    legacy_action: 'NOT AVAILABLE',
    summary_line: `${loco} · NECK: ${neck} · OSC: ${oscLabel} · PUSH: ${push}`,
  };
}

export function buildActiveEffectorsView(frame: any): ActiveEffectorsView {
  const mc = frame?.motor_control || {};
  const eff = mc.active_effectors || {};
  const physical = frame?.physical || {};
  const body = frame?.body || {};
  const orient = physical.orientation || {};
  const oscGt = physical.oscillatory_signaling?.WORLD_GT || {};
  const vx = body.vx != null ? Number(body.vx) : (physical.vx != null ? Number(physical.vx) : null);
  const vy = body.vy != null ? Number(body.vy) : (physical.vy != null ? Number(physical.vy) : null);
  const speed =
    vx != null && vy != null
      ? Math.hypot(vx, vy)
      : null;
  const rem =
    eff.osc_remaining != null
      ? Number(eff.osc_remaining)
      : oscGt.remaining != null
        ? Number(oscGt.remaining)
        : null;
  const oscActive =
    String(eff.oscillator || '').toUpperCase() === 'EMITTING'
    || (rem != null && rem > 0)
    || Boolean(oscGt.emit_active);
  const motionActive =
    String(eff.body_locomotor_force || '').toUpperCase() === 'ACTIVE'
    || (speed != null && speed > 1e-4);
  const ar = frame?.action_realization?.latest_by_agent?.[frame?.observer?.selected_agent_id || 'agent_0'];
  return {
    motion_active: motionActive,
    speed: speed != null ? speed : 'NOT AVAILABLE',
    vx: vx != null ? vx : 'NOT AVAILABLE',
    vy: vy != null ? vy : 'NOT AVAILABLE',
    head_relative_angle:
      eff.head_angle != null
        ? Number(eff.head_angle)
        : orient.head_relative_angle != null
          ? Number(orient.head_relative_angle)
          : 'NOT AVAILABLE',
    head_world_heading:
      orient.head_world_heading != null ? Number(orient.head_world_heading) : 'NOT AVAILABLE',
    head_omega:
      eff.head_omega != null
        ? Number(eff.head_omega)
        : orient.head_omega != null
          ? Number(orient.head_omega)
          : 'NOT AVAILABLE',
    neck_torque: eff.neck_torque != null ? eff.neck_torque : 'NOT AVAILABLE',
    osc_emitting: oscActive,
    osc_freq_u:
      eff.osc_freq != null
        ? Number(eff.osc_freq)
        : oscGt.osc_freq_u != null
          ? Number(oscGt.osc_freq_u)
          : 'NOT AVAILABLE',
    osc_amp_u:
      eff.osc_amp != null
        ? Number(eff.osc_amp)
        : oscGt.osc_amp_u != null
          ? Number(oscGt.osc_amp_u)
          : 'NOT AVAILABLE',
    osc_remaining: rem != null ? rem : 'NOT AVAILABLE',
    push_active: Number(eff.push_exertion || 0) > 1e-6,
    push_exertion: eff.push_exertion != null ? Number(eff.push_exertion) : 'NOT AVAILABLE',
    contact_active:
      ar?.contact_active != null ? Boolean(ar.contact_active) : 'NOT AVAILABLE',
  };
}

export function buildPassiveInputView(
  frame: any,
  agentObservation?: Record<string, number> | null,
  opts?: { attribution?: string | null },
): PassiveInputView {
  const mc = frame?.motor_control || {};
  const sens = mc.passive_input || {};
  const physical = frame?.physical || {};
  const osc = physical.oscillatory_signaling || {};
  const agent = osc.AGENT_ACCESSIBLE || {};
  const obs = agentObservation || {};
  const cogn = { ...agent, ...obs };
  const oscL = bandSeries(cogn, 'osc_l_');
  const oscR = bandSeries(cogn, 'osc_r_');
  const exo0 = cogn.exo_0 != null ? Number(cogn.exo_0) : null;
  const exo1 = cogn.exo_1 != null ? Number(cogn.exo_1) : null;
  const exo2 = cogn.exo_2 != null ? Number(cogn.exo_2) : null;
  const fieldA =
    cogn['local.FIELD_A'] != null
      ? Number(cogn['local.FIELD_A'])
      : cogn.FIELD_A != null
        ? Number(cogn.FIELD_A)
        : null;
  const fieldB =
    cogn['local.FIELD_B'] != null
      ? Number(cogn['local.FIELD_B'])
      : cogn.FIELD_B != null
        ? Number(cogn.FIELD_B)
        : null;
  const vest0 = cogn.vest_0 != null ? Number(cogn.vest_0) : null;
  const vest1 = cogn.vest_1 != null ? Number(cogn.vest_1) : null;
  const prop0 = cogn.prop_neck_0 != null ? Number(cogn.prop_neck_0) : null;
  const prop1 = cogn.prop_neck_1 != null ? Number(cogn.prop_neck_1) : null;
  const rxEnergy = [...oscL, ...oscR].reduce((a, b) => a + Math.abs(b), 0);
  const emitting = Boolean(physical.oscillatory_signaling?.WORLD_GT?.emit_active)
    || Number(mc.active_effectors?.osc_remaining || 0) > 0;
  const receiving = rxEnergy > 1e-9;
  const attr = opts?.attribution ? String(opts.attribution).toUpperCase() : null;
  return {
    vision_enabled: String(sens.vision || '').toUpperCase() === 'ACTIVE' || exo0 != null,
    exo_0: exo0 != null ? exo0 : 'NOT AVAILABLE',
    exo_1: exo1 != null ? exo1 : 'NOT AVAILABLE',
    exo_2: exo2 != null ? exo2 : 'NOT AVAILABLE',
    vision_radius:
      physical.near_field_exteroception?.vision_radius != null
        ? Number(physical.near_field_exteroception.vision_radius)
        : 'NOT AVAILABLE',
    osc_l: oscL,
    osc_r: oscR,
    osc_rx_active: String(sens.osc_reception || '').toUpperCase() === 'ACTIVE' || receiving,
    field_a: fieldA != null ? fieldA : 'NOT AVAILABLE',
    field_b: fieldB != null ? fieldB : 'NOT AVAILABLE',
    legacy_fields_present:
      String(sens.legacy_fields || '').toUpperCase() === 'ACTIVE'
      || fieldA != null
      || fieldB != null,
    vest_0: vest0 != null ? vest0 : 'NOT AVAILABLE',
    vest_1: vest1 != null ? vest1 : 'NOT AVAILABLE',
    prop_neck_0: prop0 != null ? prop0 : 'NOT AVAILABLE',
    prop_neck_1: prop1 != null ? prop1 : 'NOT AVAILABLE',
    emitting,
    receiving,
    observer_gt_rx_provenance:
      attr && (attr === 'SELF' || attr === 'CROSS' || attr === 'MIXED' || attr.includes('SELF') || attr.includes('CROSS') || attr.includes('MIXED'))
        ? attr
        : 'NOT AVAILABLE',
  };
}

export function buildObserveCurrentState(
  frame: any,
  opts?: {
    run_id?: string | null;
    agent_id?: string | null;
    agentObservation?: Record<string, number> | null;
    attribution?: string | null;
  },
): ObserveCurrentState {
  return {
    provenance: buildObserveProvenance(frame, opts),
    motor: buildMotorOutputView(frame),
    effectors: buildActiveEffectorsView(frame),
    passive: buildPassiveInputView(frame, opts?.agentObservation, {
      attribution: opts?.attribution,
    }),
  };
}

/** True when OSC command has no emit trigger but physical emission remains active. */
export function oscTriggerAbsentWhileActive(state: ObserveCurrentState): boolean {
  return state.motor.osc_emit_trigger === false && state.effectors.osc_emitting === true;
}

/** MOVE + active OSC emission coexistence. */
export function moveAndOscEmissionCoexist(state: ObserveCurrentState): boolean {
  return String(state.motor.locomotion).startsWith('MOVE:') && state.effectors.osc_emitting;
}

/** Emission + reception full-duplex on same tick. */
export function emittingAndReceiving(state: ObserveCurrentState): boolean {
  return state.passive.emitting && state.passive.receiving;
}
