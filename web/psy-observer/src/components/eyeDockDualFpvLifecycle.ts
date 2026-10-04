/** Pure Dual FPV lifecycle helpers — researcher display ownership only. */

export type ExactTraceLike = {
  agent_id?: string;
  trace_id?: string;
  observation_tick?: number | null;
  receptor_tick?: number | null;
  runtime_generation?: number | null;
  true_zero_exact_trace?: boolean;
  [key: string]: unknown;
};

export function liveState(latest: ExactTraceLike | null | undefined): 'LIVE' | 'ZERO' | 'UNAVAILABLE' {
  if (!latest) return 'UNAVAILABLE';
  if (latest.true_zero_exact_trace) return 'ZERO';
  return 'LIVE';
}

/** Merge incoming dual-map entries into retained cache. Never cross-copy agents. Never clear on omission. */
export function absorbLatestExactByAgent(
  retained: Record<string, ExactTraceLike>,
  incoming: Record<string, ExactTraceLike> | null | undefined,
): Record<string, ExactTraceLike> {
  if (!incoming || typeof incoming !== 'object') return retained;
  for (const [agentId, tr] of Object.entries(incoming)) {
    if (!tr || typeof tr !== 'object') continue;
    if (String(tr.agent_id || agentId) !== String(agentId)) continue;
    retained[String(agentId)] = tr;
  }
  return retained;
}

/** Resolve exact trace for one card. Prefer live map, then retained, then selected-latest match only. */
export function traceForAgent(
  view: any,
  agentId: string,
  retained: Record<string, ExactTraceLike>,
): ExactTraceLike | null {
  const map = view?.latest_exact_by_agent;
  if (map && typeof map === 'object' && map[agentId]) {
    const tr = map[agentId];
    if (tr && String(tr.agent_id || agentId) === String(agentId)) return tr;
  }
  const kept = retained[agentId];
  if (kept && String(kept.agent_id || agentId) === String(agentId)) return kept;
  const latest = view?.latest;
  if (latest && String(latest.agent_id || view?.selected_agent_id) === String(agentId)) {
    return latest;
  }
  return null;
}

/** Dock-owned dual FPV interest: dock open or central Vision/Hearing owns sensory. */
export function wantEyeDockDualFpvSubscription(args: {
  open: boolean;
  centralOwnsSensory?: string | null;
}): boolean {
  const central = args.centralOwnsSensory;
  return Boolean(args.open) || central === 'VISION' || central === 'HEARING';
}
