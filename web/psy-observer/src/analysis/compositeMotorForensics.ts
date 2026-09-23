/**
 * COMPOSITE MOTOR FORENSICS — Analyzer/Observer only.
 * Reconstructs factorized motor domains from scientific_rows + events.
 * Does not invent Cartesian compound action tokens.
 */
export type CompositeMotorForensics = {
  schema: 'COMPOSITE_MOTOR_V1' | 'LEGACY_SINGLE_SLOT';
  authoritative: boolean;
  agents: Record<string, any>;
  named_combinations: Record<string, number>;
  control_vs_effector_totals: Record<string, Record<string, number>>;
  note: string;
};

type Row = Record<string, any>;
type Ev = Record<string, any>;

function detectSchema(rows: Row[], events: Ev[]): CompositeMotorForensics['schema'] {
  for (const r of rows.slice(0, 500)) {
    if (String(r.action_source || '').toUpperCase().includes('COMPOSITE')) return 'COMPOSITE_MOTOR_V1';
    if (r.motor_schema === 'COMPOSITE_MOTOR_V1' || r.motor_output) return 'COMPOSITE_MOTOR_V1';
  }
  for (const ev of events.slice(0, 2000)) {
    const e = ev.evidence || {};
    if (String(e.selection_source || e.source || '').toUpperCase().includes('COMPOSITE')) {
      return 'COMPOSITE_MOTOR_V1';
    }
  }
  return 'LEGACY_SINGLE_SLOT';
}

function indexEvents(events: Ev[]) {
  const m = new Map<string, Ev[]>();
  for (const ev of events) {
    const t = Number(ev.tick);
    if (!Number.isFinite(t)) continue;
    const e = ev.evidence || {};
    for (const aid of [ev.agent_id, e.actor_agent_id, e.emitter_agent_id]) {
      if (!aid) continue;
      const k = `${aid}|${t}`;
      const arr = m.get(k) || [];
      arr.push(ev);
      m.set(k, arr);
    }
  }
  return m;
}

function reconstruct(row: Row, tickEvents: Ev[], schema: string) {
  if (row.motor_output && typeof row.motor_output === 'object') {
    return {
      locomotion: row.motor_output.locomotion || 'WAIT',
      neck: row.motor_output.neck || 'NONE',
      oscillator: row.motor_output.oscillator || { emit_trigger: false },
      push: !!row.motor_output.push,
      legacy: row.motor_output.legacy_token || row.action,
    };
  }
  const action = String(row.action || 'WAIT');
  let loco = 'WAIT';
  let neck = 'NONE';
  let push = false;
  const osc: any = { frequency_delta: 0, amplitude_delta: 0, emit_trigger: false };
  if (action.startsWith('MOVE:')) loco = action;
  else if (action.startsWith('NECK_')) neck = action;
  else if (action === 'PUSH') push = true;
  else if (action === 'OSC_EMIT') osc.emit_trigger = true;
  else if (action === 'OSC_FREQ_UP') osc.frequency_delta = 1;
  else if (action === 'OSC_FREQ_DOWN') osc.frequency_delta = -1;
  else if (action === 'OSC_AMP_UP') osc.amplitude_delta = 1;
  else if (action === 'OSC_AMP_DOWN') osc.amplitude_delta = -1;

  for (const ev of tickEvents) {
    const typ = String(ev.type || '');
    const e = ev.evidence || {};
    if (typ === 'NECK_MOTOR_APPLIED' || typ === 'NECK_TORQUE_APPLIED') {
      const u = Number(e.neck_motor);
      if (Number.isFinite(u)) {
        if (u > 1e-9) neck = 'NECK_LEFT';
        else if (u < -1e-9) neck = 'NECK_RIGHT';
        else if (neck === 'NONE') neck = 'NECK_HOLD';
      } else if (neck === 'NONE') neck = 'NECK_HOLD';
    }
    if (typ === 'PUSH_EXERTED') push = true;
    if (typ === 'OSC_EMISSION_STARTED') osc.emit_trigger = true;
  }
  return { locomotion: loco, neck, oscillator: osc, push, legacy: action, schema };
}

function comboKey(m: any): string {
  const parts: string[] = [];
  if (String(m.locomotion || '').startsWith('MOVE:')) parts.push('MOVE');
  if (m.neck && m.neck !== 'NONE') parts.push('NECK');
  const o = m.oscillator || {};
  if (o.emit_trigger) parts.push('OSC_EMIT');
  else if (o.frequency_delta || o.amplitude_delta) parts.push('OSC_CTRL');
  if (m.push) parts.push('PUSH');
  return parts.length ? parts.join('+') : 'WAIT/NONE';
}

export function buildCompositeMotorForensics(
  rows: Row[] | undefined,
  events: Ev[] | undefined,
  cutoff?: number | null,
): CompositeMotorForensics {
  const r = rows || [];
  const evs = events || [];
  const schema = detectSchema(r, evs);
  const idx = indexEvents(evs);
  const agents: Record<string, any> = {};
  const named: Record<string, number> = {
    'MOVE+NECK': 0,
    'MOVE+OSC_EMIT': 0,
    'MOVE+PUSH': 0,
    'MOVE+NECK+OSC': 0,
    'MOVE+NECK+OSC+PUSH': 0,
  };
  const totals: any = {
    emit_triggers: {} as Record<string, number>,
    emission_active_ticks: {} as Record<string, number>,
    neck_commands: {} as Record<string, number>,
    head_rotating_ticks: {} as Record<string, number>,
  };

  for (const row of r) {
    const t = Number(row.tick);
    if (cutoff != null && Number.isFinite(cutoff) && t > Number(cutoff)) continue;
    const aid = String(row.agent_id || 'agent_0');
    const ag = (agents[aid] ||= {
      locomotion_ticks: 0,
      neck_control_ticks: 0,
      oscillator_control_ticks: 0,
      emission_trigger_ticks: 0,
      push_ticks: 0,
      wait_no_intervention_ticks: 0,
      combinations: {} as Record<string, number>,
      legacy_projection_counts: {} as Record<string, number>,
      control_vs_effector: {
        OSC_EMIT_selections: 0,
        emission_active_ticks: 0,
        neck_commands: 0,
        head_rotating_ticks: 0,
      },
    });
    const te = idx.get(`${aid}|${t}`) || [];
    const m = reconstruct(row, te, schema);
    if (String(m.locomotion).startsWith('MOVE:')) ag.locomotion_ticks++;
    if (m.neck !== 'NONE') {
      ag.neck_control_ticks++;
      ag.control_vs_effector.neck_commands++;
      totals.neck_commands[aid] = (totals.neck_commands[aid] || 0) + 1;
    }
    const o = m.oscillator || {};
    if (o.emit_trigger || o.frequency_delta || o.amplitude_delta) ag.oscillator_control_ticks++;
    if (o.emit_trigger) {
      ag.emission_trigger_ticks++;
      ag.control_vs_effector.OSC_EMIT_selections++;
      totals.emit_triggers[aid] = (totals.emit_triggers[aid] || 0) + 1;
    }
    if (m.push) ag.push_ticks++;
    if (
      (m.locomotion === 'WAIT' || m.locomotion === 'NONE')
      && m.neck === 'NONE'
      && !o.emit_trigger
      && !o.frequency_delta
      && !o.amplitude_delta
      && !m.push
    ) {
      ag.wait_no_intervention_ticks++;
    }
    const ck = comboKey(m);
    ag.combinations[ck] = (ag.combinations[ck] || 0) + 1;
    ag.legacy_projection_counts[String(m.legacy)] = (ag.legacy_projection_counts[String(m.legacy)] || 0) + 1;

    if (row.osc_emit_active || Number(row.osc_emit_remaining || 0) > 0) {
      ag.control_vs_effector.emission_active_ticks++;
      totals.emission_active_ticks[aid] = (totals.emission_active_ticks[aid] || 0) + 1;
    }
    if (Math.abs(Number(row.head_omega || 0)) > 1e-6) {
      ag.control_vs_effector.head_rotating_ticks++;
      totals.head_rotating_ticks[aid] = (totals.head_rotating_ticks[aid] || 0) + 1;
    }

    const parts = new Set(ck.split('+'));
    if (parts.has('MOVE') && parts.has('NECK') && !parts.has('OSC_EMIT') && !parts.has('OSC_CTRL') && !parts.has('PUSH')) {
      named['MOVE+NECK']++;
    }
    if (parts.has('MOVE') && parts.has('OSC_EMIT') && !parts.has('NECK') && !parts.has('PUSH')) {
      named['MOVE+OSC_EMIT']++;
    }
    if (parts.has('MOVE') && parts.has('PUSH') && !parts.has('NECK') && !parts.has('OSC_EMIT') && !parts.has('OSC_CTRL')) {
      named['MOVE+PUSH']++;
    }
    if (parts.has('MOVE') && parts.has('NECK') && (parts.has('OSC_EMIT') || parts.has('OSC_CTRL')) && !parts.has('PUSH')) {
      named['MOVE+NECK+OSC']++;
    }
    if (parts.has('MOVE') && parts.has('NECK') && (parts.has('OSC_EMIT') || parts.has('OSC_CTRL')) && parts.has('PUSH')) {
      named['MOVE+NECK+OSC+PUSH']++;
    }
  }

  return {
    schema,
    authoritative: schema === 'COMPOSITE_MOTOR_V1',
    agents,
    named_combinations: named,
    control_vs_effector_totals: totals,
    note:
      'SELECTED MOTOR OUTPUT ≠ ACTIVE PHYSICAL EFFECTORS. '
      + 'Canonical action labels are LEGACY PROJECTION when composite is authoritative.',
  };
}
