/**
 * Atomic multi-agent observer projection.
 * Never mix identity from one agent with body/mind/seed from another.
 */
export type IdentityTuple = {
  runtime_generation: number | null;
  inspected_tick: number | null;
  selected_agent_id: string;
};

export type ProjectionResult = {
  ok: boolean;
  agent_id: string;
  body_id: string;
  agent_seed: number | null;
  tick: number | null;
  generation: number | null;
  mind: Record<string, any>;
  body: Record<string, any> | null;
  physical: Record<string, any> | null;
  causal_chain: Record<string, any> | null;
  cognition_pipeline: Record<string, any> | null;
  prospection_view: Record<string, any> | null;
  perception: Record<string, any> | null;
  reason?: string;
};

export function canonicalBodyId(agentId: string): string {
  const m = /^agent_(\d+)$/.exec(String(agentId));
  return m ? `body-${m[1]}` : 'body-0';
}

export function frameTick(frame: any): number | null {
  const t = frame?.header?.tick ?? frame?.observer?.inspected_tick ?? frame?.observer?.identity_tuple?.inspected_tick;
  return t == null || t === '' ? null : Number(t);
}

export function frameGeneration(frame: any): number | null {
  const g = frame?.header?.runtime_generation
    ?? frame?.observer?.runtime_generation
    ?? frame?.observer?.identity_tuple?.runtime_generation
    ?? frame?.observation?.runtime_generation;
  return g == null || g === '' ? null : Number(g);
}

export function requestedAgentId(frame: any, override?: string | null): string {
  if (override) return String(override);
  return String(
    frame?.observer?.selected_agent_id
    || frame?.header?.selected_agent_id
    || frame?.header?.selected_agent
    || 'agent_0',
  );
}

/** Reject projections that do not match the requested agent identity. */
export function validateAgentView(
  view: any,
  agentId: string,
  expectedTick: number | null,
  expectedGeneration: number | null,
): { ok: true } | { ok: false; reason: string } {
  if (!view || typeof view !== 'object') {
    return { ok: false, reason: `NOT RECORDED: agents_views[${agentId}] missing` };
  }
  if (String(view.agent_id || '') !== agentId) {
    return { ok: false, reason: `identity mismatch: view.agent_id=${view.agent_id} != ${agentId}` };
  }
  const wantBody = canonicalBodyId(agentId);
  if (String(view.body_id || view.body?.body_id || view.body?.id || '') !== wantBody) {
    return {
      ok: false,
      reason: `body mismatch: expected ${wantBody}, got ${view.body_id || view.body?.body_id || view.body?.id}`,
    };
  }
  if (view.body && String(view.body.agent_id || '') && String(view.body.agent_id) !== agentId) {
    return { ok: false, reason: `body.agent_id=${view.body.agent_id} != ${agentId}` };
  }
  const mind = view.mind || {};
  const src = mind.source_agent_id || mind.agent_id;
  if (mind && Object.keys(mind).length && src && String(src) !== agentId) {
    return { ok: false, reason: `mind source ${src} != ${agentId}` };
  }
  // Cognitive payload without source is unverifiable — refuse (prevents stale leak)
  const cognitiveKeys = ['memory', 'predictive_organization', 'prospection', 'instrumental_observation', 'metrics', 'causal_trace', 'action', 'bridges'];
  const hasCognitive = cognitiveKeys.some((k) => mind[k] != null);
  if (hasCognitive && mind.status !== 'NOT AVAILABLE' && mind.status !== 'INACTIVE' && !src) {
    return { ok: false, reason: 'mind payload present without source_agent_id — refusing unverifiable data' };
  }
  if (expectedTick != null && view.tick != null && Number(view.tick) !== Number(expectedTick)) {
    return { ok: false, reason: `tick mismatch: view ${view.tick} != frame ${expectedTick}` };
  }
  if (expectedGeneration != null && view.generation != null && Number(view.generation) !== Number(expectedGeneration)) {
    return { ok: false, reason: `generation mismatch: view ${view.generation} != frame ${expectedGeneration}` };
  }
  return { ok: true };
}

function unavailableMind(agentId: string, reason: string): Record<string, any> {
  return {
    status: 'NOT AVAILABLE',
    source_agent_id: agentId,
    agent_id: agentId,
    body_id: canonicalBodyId(agentId),
    reason,
  };
}

/**
 * Build a coherent selected-agent projection from agents_views.
 * On failure: explicit NOT AVAILABLE mind and null body/physical — never reuse previous agent data.
 */
export function resolveSelectedProjection(frame: any, agentId: string): ProjectionResult {
  const tick = frameTick(frame);
  const generation = frameGeneration(frame);
  const view = frame?.agents_views?.[agentId];
  const checked = validateAgentView(view, agentId, tick, generation);
  if (!checked.ok) {
    return {
      ok: false,
      agent_id: agentId,
      body_id: canonicalBodyId(agentId),
      agent_seed: null,
      tick,
      generation,
      mind: unavailableMind(agentId, checked.reason),
      body: null,
      physical: null,
      causal_chain: null,
      cognition_pipeline: null,
      prospection_view: null,
      perception: null,
      reason: checked.reason,
    };
  }
  const mind = { ...(view.mind || {}) };
  if (!mind.source_agent_id) mind.source_agent_id = agentId;
  if (!mind.agent_id) mind.agent_id = agentId;
  if (!mind.body_id) mind.body_id = canonicalBodyId(agentId);
  const seed = view.agent_seed != null ? Number(view.agent_seed) : (mind.agent_seed != null ? Number(mind.agent_seed) : null);
  return {
    ok: true,
    agent_id: agentId,
    body_id: canonicalBodyId(agentId),
    agent_seed: seed,
    tick: view.tick != null ? Number(view.tick) : tick,
    generation: view.generation != null ? Number(view.generation) : generation,
    mind,
    body: view.body || null,
    physical: view.physical || null,
    causal_chain: view.causal_chain || null,
    cognition_pipeline: view.cognition_pipeline || null,
    prospection_view: view.prospection_view || null,
    perception: view.perception || null,
  };
}

/**
 * Apply selected projection onto a frame copy for rendering.
 * Clears agent-specific top-level fields when unavailable — no stale reuse.
 */
export function applyProjectionToFrame(base: any, agentId: string): any {
  const proj = resolveSelectedProjection(base, agentId);
  const generation = proj.generation ?? frameGeneration(base);
  const tick = proj.tick ?? frameTick(base);
  const identity: IdentityTuple = {
    runtime_generation: generation,
    inspected_tick: tick,
    selected_agent_id: agentId,
  };
  return {
    ...base,
    mind: proj.mind,
    body: proj.body || {
      id: proj.body_id,
      body_id: proj.body_id,
      agent_id: agentId,
      status: 'NOT AVAILABLE',
      reason: proj.reason || 'body projection unavailable',
    },
    physical: proj.physical || { source_agent_id: agentId, body_id: proj.body_id, status: 'NOT AVAILABLE' },
    causal_chain: proj.causal_chain || { status: 'NOT AVAILABLE', reason: proj.reason },
    cognition_pipeline: proj.cognition_pipeline || { status: 'NOT AVAILABLE', stages: [] },
    prospection_view: proj.prospection_view || { status: 'NOT AVAILABLE', branches: [] },
    perception: proj.perception || { status: 'NOT AVAILABLE', reason: proj.reason },
    // Keep agents_views intact for COMPARE / re-projection
    agents_views: base?.agents_views,
    signal_forensics: projectSignalForensics(base?.signal_forensics, agentId, base?.structured_events),
    header: {
      ...(base?.header || {}),
      selected_agent_id: agentId,
      selected_agent: agentId,
      selected_body_id: proj.body_id,
      // Never fall back to base experiment seed for the wrong agent
      inspected_agent_seed: proj.agent_seed,
      runtime_generation: generation ?? base?.header?.runtime_generation,
      tick: tick ?? base?.header?.tick,
    },
    observer: {
      ...(base?.observer || {}),
      selected_agent_id: agentId,
      selected_body_id: proj.body_id,
      inspected_tick: tick,
      runtime_generation: generation,
      identity_tuple: {
        ...identity,
        selected_body_id: proj.body_id,
        agent_seed: proj.agent_seed,
      },
      projection_ok: proj.ok,
      projection_reason: proj.reason,
    },
    _projection: proj,
  };
}

function projectSignalForensics(forensics: any, agentId: string, events: any[] | undefined) {
  if (!forensics || typeof forensics !== 'object') {
    return {
      selected_agent_id: agentId,
      signals_emitted: [],
      signals_received: [],
      note: 'Physical signals only — not communication.',
    };
  }
  // If forensics already targets this agent, keep; otherwise filter rows by agent id.
  const emitted = (forensics.signals_emitted || []).filter((r: any) => !r.agent || r.agent === agentId);
  const received = (forensics.signals_received || []).filter((r: any) => !r.agent || r.agent === agentId);
  if (forensics.selected_agent_id && forensics.selected_agent_id !== agentId) {
    // Rebuild lightly from structured events if present
    const ev = Array.isArray(events) ? events : [];
    const outE: any[] = [];
    const outR: any[] = [];
    for (const e of ev) {
      const et = String(e.type || e.kind || '');
      const aid = e.actor_agent_id || e.agent_id || e.emitter_agent_id || e.receiver_agent_id;
      if (aid !== agentId) continue;
      const evidence = e.evidence || {};
      const row = {
        tick: e.tick,
        agent: aid,
        channel: evidence.channel || evidence.field,
        intensity: evidence.intensity || evidence['local.FIELD_A'] || evidence['local.FIELD_B'],
        counterparty: evidence.source_agent_id || evidence.emitter_agent_id || 'UNKNOWN',
        pairing: 'PAIRING NOT DEMONSTRATED',
        evidence,
      };
      if (et.includes('EMITTED')) outE.push(row);
      if (et.includes('RECEIVED')) outR.push(row);
    }
    return {
      selected_agent_id: agentId,
      signals_emitted: outE.slice(-20),
      signals_received: outR.slice(-20),
      note: forensics.note || 'Physical signals only — not communication.',
    };
  }
  return {
    ...forensics,
    selected_agent_id: agentId,
    signals_emitted: emitted,
    signals_received: received,
  };
}

/** True if incoming live frame should replace current given selection sequencing. */
export function shouldAcceptLiveFrame(
  incoming: any,
  opts: {
    desiredAgentId: string | null;
    selectionSeq: number;
    lastAcceptedSeq: number;
    mode: string;
  },
): boolean {
  if (opts.mode !== 'LIVE') return false;
  // Always accept if no pending selection preference
  if (!opts.desiredAgentId) return true;
  const incomingAgent = requestedAgentId(incoming);
  // If a newer selection was requested, ignore frames that still advertise the old agent
  // only when selectionSeq advanced after last accept — stale in-flight captures.
  if (opts.selectionSeq > opts.lastAcceptedSeq && incomingAgent !== opts.desiredAgentId) {
    // Still accept if agents_views can re-project to desired agent at this tick
    const views = incoming?.agents_views || {};
    if (views[opts.desiredAgentId]) return true;
    return false;
  }
  return true;
}

export function compareViewsSameFrame(frame: any): {
  ok: boolean;
  tick: number | null;
  generation: number | null;
  agent_0: ProjectionResult;
  agent_1: ProjectionResult;
  reason?: string;
} {
  const tick = frameTick(frame);
  const generation = frameGeneration(frame);
  const a0 = resolveSelectedProjection(frame, 'agent_0');
  const a1 = resolveSelectedProjection(frame, 'agent_1');
  if (!a0.ok || !a1.ok) {
    return {
      ok: false,
      tick,
      generation,
      agent_0: a0,
      agent_1: a1,
      reason: a0.reason || a1.reason || 'COMPARE unavailable',
    };
  }
  if (a0.tick != null && a1.tick != null && a0.tick !== a1.tick) {
    return { ok: false, tick, generation, agent_0: a0, agent_1: a1, reason: 'COMPARE tick mismatch' };
  }
  if (a0.generation != null && a1.generation != null && a0.generation !== a1.generation) {
    return { ok: false, tick, generation, agent_0: a0, agent_1: a1, reason: 'COMPARE generation mismatch' };
  }
  return { ok: true, tick, generation, agent_0: a0, agent_1: a1 };
}
