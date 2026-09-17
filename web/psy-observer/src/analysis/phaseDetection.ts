import type { AnalysisState } from './aggregates.ts';
import type { Phase } from './types.ts';

/**
 * Phase detection from measurable regime changes (action mobility + contact).
 * Names describe behavior, not psychology.
 */
export function detectPhases(state: AnalysisState): Phase[] {
  const start = state.start_tick ?? 0;
  const end = state.end_tick ?? start;
  if (end <= start) {
    return [{ start, end, name: 'INSUFFICIENT DATA', reason: 'No tick span available.' }];
  }
  const span = end - start;
  const phases: Phase[] = [];

  // Windowed mobility from agent action counts is coarse; use contact episodes + firsts.
  const firstMove = Math.min(
    ...Object.values(state.agents)
      .map((a) => a.first_move_tick)
      .filter((t): t is number => t != null),
    end + 1,
  );
  const contact0 = state.first_contact_tick;

  let cursor = start;
  if (firstMove !== end + 1 && firstMove > start) {
    phases.push({
      start: cursor,
      end: Math.max(cursor, firstMove - 1),
      name: 'PRE-MOVEMENT',
      reason: 'No MOVE selections observed before first MOVE tick.',
    });
    cursor = firstMove;
  }

  if (contact0 != null && contact0 > cursor) {
    phases.push({
      start: cursor,
      end: contact0 - 1,
      name: 'PRE-CONTACT MOBILITY',
      reason: 'MOVE observed; body-body contact not yet recorded.',
    });
    cursor = contact0;
  }

  if (contact0 != null) {
    const ep = state.contact_episodes;
    const lastEpEnd = ep.length ? ep[ep.length - 1].end : contact0;
    const contactEnd = Math.min(end, Math.max(lastEpEnd, contact0 + Math.floor(span * 0.05)));
    phases.push({
      start: cursor,
      end: contactEnd,
      name: 'CONTACT-ASSOCIATED PERIOD',
      reason: `Body-body contact present (first at t${contact0}; ${state.contact_ticks} contact timeline ticks).`,
    });
    cursor = contactEnd + 1;
  }

  // Divergent WAIT rates if multi-agent
  const ag = Object.values(state.agents);
  if (ag.length >= 2 && cursor <= end) {
    const w0 = Number(ag[0].action_counts.WAIT || 0);
    const t0 = Object.values(ag[0].action_counts).reduce((s, v) => s + v, 0) || 1;
    const w1 = Number(ag[1].action_counts.WAIT || 0);
    const t1 = Object.values(ag[1].action_counts).reduce((s, v) => s + v, 0) || 1;
    if (Math.abs(w0 / t0 - w1 / t1) > 0.2) {
      phases.push({
        start: cursor,
        end,
        name: 'DIVERGENT ACTION PATTERNS',
        reason: `WAIT rates differ by >20pp across agents (${ag[0].agent_id} vs ${ag[1].agent_id}).`,
      });
      cursor = end + 1;
    }
  }

  if (cursor <= end) {
    const waitHeavy = ag.some((a) => {
      const w = Number(a.action_counts.WAIT || 0);
      const t = Object.values(a.action_counts).reduce((s, v) => s + v, 0) || 1;
      return w / t > 0.7;
    });
    phases.push({
      start: cursor,
      end,
      name: waitHeavy ? 'LOW-MOBILITY PERIOD' : 'CONTINUED ACTIVITY',
      reason: waitHeavy
        ? 'At least one agent WAIT rate >70% over run aggregates.'
        : 'Remaining tick span after prior regime markers.',
    });
  }

  // Merge tiny phases
  const merged: Phase[] = [];
  for (const p of phases) {
    if (p.end < p.start) continue;
    const prev = merged[merged.length - 1];
    if (prev && p.start - prev.end <= 1 && p.name === prev.name) {
      prev.end = p.end;
      continue;
    }
    merged.push({ ...p });
  }
  return merged.slice(0, 24);
}
