import { BOUNDS } from './aggregates.ts';
import type { AnalysisState } from './aggregates.ts';
import type { ImportantEvent, InteractionSummary, OverviewCard, Phase } from './types.ts';

export function buildOverview(
  state: AnalysisState,
  important: ImportantEvent[],
  phases: Phase[],
  interactions: InteractionSummary,
): OverviewCard[] {
  const cards: OverviewCard[] = [];
  const start = state.start_tick ?? 0;
  const end = state.end_tick ?? start;
  const agents = Object.values(state.agents).sort((a, b) => a.agent_id.localeCompare(b.agent_id));

  cards.push({
    id: 'begin',
    kind: 'KEY',
    tick_start: start,
    tick_end: start,
    title: 'SIMULATION WINDOW',
    body: agents.length >= 2
      ? `The observer window covers ticks ${start}–${end} with ${agents.length} agents. `
        + agents.map((a) => `${a.agent_id}: ${a.body_id}, seed ${a.seed ?? 'NOT AVAILABLE'}`).join('; ')
        + '.'
      : `The observer window covers ticks ${start}–${end} for agent_0 (${agents[0]?.body_id || 'body-0'}).`,
    category: 'PHYSICAL',
    agent_filter: agents.map((a) => a.agent_id),
    evidence_class: 'OBSERVED',
    evidence: { tick: start, agent_ids: agents.map((a) => a.agent_id), frame_tick: start },
    keyframe: state.keyframes.find((k) => k.tick === start) || null,
  });

  for (const ev of important) {
    if (ev.category === 'EXTREMA' && cards.length > 40) continue;
    const kf = state.keyframes.find((k) => k.tick === ev.tick) || null;
    cards.push({
      id: `imp-${ev.tick}-${ev.kind}`,
      kind: 'KEY',
      tick_start: ev.tick,
      tick_end: ev.tick,
      title: ev.title,
      body: narrativeForImportant(ev),
      category: categoryFor(ev.kind),
      agent_filter: ev.agent_ids || [],
      evidence_class: ev.evidence_class,
      evidence: {
        tick: ev.tick,
        event_ids: ev.event_ids,
        agent_ids: ev.agent_ids,
        body_ids: ev.body_ids,
        emission_ids: ev.emission_ids,
        frame_tick: ev.tick,
      },
      keyframe: kf,
    });
  }

  // Compress long WAIT streaks into episodes
  for (const agg of agents) {
    if (agg.cognitive_wait_selections >= 15) {
      cards.push({
        id: `cog-wait-${agg.agent_id}`,
        kind: 'EPISODE',
        tick_start: start,
        tick_end: end,
        title: `COGNITIVE WAIT SELECTIONS (${agg.agent_id})`,
        body: `${agg.agent_id} selected WAIT through PROSPECTIVE_SCENARIO (or related PROSPECTIVE_* source) `
          + `for ${agg.cognitive_wait_selections} observed decisions in this window (OBSERVED via SCENARIO_SELECTED). `
          + `WAIT denotes the mechanism-defined action only — no psychological claim.`,
        category: 'COGNITION',
        agent_filter: [agg.agent_id],
        evidence_class: 'OBSERVED',
        evidence: {
          tick: end,
          agent_ids: [agg.agent_id],
          frame_tick: end,
        },
        keyframe: null,
      });
    } else if (agg.longest_wait_streak >= 15) {
      const t1 = agg.first_wait_after_move_tick ?? Math.max(start, end - agg.longest_wait_streak);
      cards.push({
        id: `wait-ep-${agg.agent_id}`,
        kind: 'EPISODE',
        tick_start: t1,
        tick_end: Math.min(end, t1 + agg.longest_wait_streak - 1),
        title: `PROLONGED WAIT (${agg.agent_id})`,
        body: `${agg.agent_id} selected WAIT for up to ${agg.longest_wait_streak} consecutive ticks (DERIVED from timeline action streaks). `
          + `No psychological interpretation is implied.`,
        category: 'ACTION',
        agent_filter: [agg.agent_id],
        evidence_class: 'DERIVED',
        evidence: { tick: t1, agent_ids: [agg.agent_id], frame_tick: t1 },
        keyframe: null,
      });
    }
  }

  // Quiet spans between key cards
  const keyTicks = [...new Set(cards.filter((c) => c.kind === 'KEY').map((c) => c.tick_start))].sort((a, b) => a - b);
  for (let i = 0; i < keyTicks.length - 1; i++) {
    const a = keyTicks[i];
    const b = keyTicks[i + 1];
    if (b - a > BOUNDS.quiet_episode_merge_gap) {
      cards.push({
        id: `quiet-${a}-${b}`,
        kind: 'QUIET',
        tick_start: a + 1,
        tick_end: b - 1,
        title: 'NO MAJOR TRANSITION DETECTED',
        body: `Ticks ${a + 1}–${b - 1}: no additional FIRST/TRANSITION markers between recorded important events. `
          + `Agents continued their previously observed action regimes (compressed).`,
        category: 'ACTION',
        agent_filter: [],
        evidence_class: 'DERIVED',
        evidence: { tick: a + 1, frame_tick: a + 1 },
        keyframe: null,
      });
    }
  }

  for (const ph of phases) {
    cards.push({
      id: `phase-${ph.start}-${ph.name}`,
      kind: 'PHASE',
      tick_start: ph.start,
      tick_end: ph.end,
      title: ph.name,
      body: `Phase ${ph.start}–${ph.end}: ${ph.reason}`,
      category: 'PHYSICAL',
      agent_filter: [],
      evidence_class: 'DERIVED',
      evidence: { tick: ph.start, frame_tick: ph.start },
      keyframe: null,
    });
  }

  if (interactions.cross_agent_contributions > 0) {
    cards.push({
      id: 'cross-summary',
      kind: 'EPISODE',
      tick_start: start,
      tick_end: end,
      title: 'CROSS-AGENT PHYSICAL SIGNAL COUPLING',
      body: `${interactions.cross_agent_contributions} reception records listed a same-tick contributing emission from the other agent. `
        + `Source attribution remains mixed / not uniquely attributable under continuum fields. `
        + `This is physical coupling, not demonstrated communication.`,
      category: 'SIGNAL',
      agent_filter: ['agent_0', 'agent_1'],
      evidence_class: 'CAUSALLY_LINKED',
      evidence: { tick: end, agent_ids: ['agent_0', 'agent_1'], frame_tick: end },
      keyframe: null,
    });
  }

  return cards
    .sort((a, b) => a.tick_start - b.tick_start || a.kind.localeCompare(b.kind))
    .slice(0, BOUNDS.max_overview_cards);
}

function narrativeForImportant(ev: ImportantEvent): string {
  const base = `${ev.title} at tick ${ev.tick}. ${ev.reason}`;
  if (ev.kind.includes('CONTACT')) {
    return `${base} Soft body-body contact does not imply semantic communication.`;
  }
  if (ev.kind.includes('CROSS_AGENT')) {
    return `${base} Continuum field attribution is mixed unless provenance says otherwise.`;
  }
  return base;
}

function categoryFor(kind: string): string {
  if (kind.includes('SIGNAL') || kind.includes('CROSS_AGENT')) return 'SIGNAL';
  if (kind.includes('CONTACT')) return 'INTERACTION';
  if (kind.includes('MOVE') || kind.includes('WAIT')) return 'ACTION';
  if (kind.includes('PREDICTION') || kind.includes('PROSPECTIVE') || kind.includes('SCENARIO')) return 'COGNITION';
  if (kind.includes('RESOURCE') || kind.includes('WORK')) return 'RESOURCE';
  if (kind.includes('DEFORM')) return 'BODY';
  return 'FIRSTS';
}
