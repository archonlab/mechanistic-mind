/**
 * Analyzer vision forensics — optical provenance without claiming recognition.
 *
 * Authority: compact vision_optical records derived from sample_near_field
 * (same function Sensor Inspector / NearFieldSensorPanel consumes).
 * Analyzer does NOT reimplement FOV / distance / illumination / soft-OR.
 */
import type { AnalysisState } from './aggregates.ts';
import type { AgentAnalysis, CausalChain, EvidenceClass, ImportantEvent, NaMetric } from './types.ts';

/** Float-dust floor — not a perceptual threshold. Matches backend BODY_OPTICAL_EPS. */
export const BODY_OPTICAL_EPS = 1e-12;

export type OpticalNeighborTS = {
  cell: number[];
  inside_fov: boolean;
  surface_response: number;
  body_optical: number;
  composed_optical: number;
  final_contribution: number;
  relative_angle_deg?: number;
  distance?: number;
  detectable?: boolean;
  source_body_ids?: string[];
};

export type OpticalTickTS = {
  tick: number;
  observer_body_id: string;
  observer_agent_id?: string;
  theta?: number;
  exo: Record<string, number>;
  illumination?: number;
  vision_enabled?: boolean;
  body_optics_enabled?: boolean;
  neighbors: OpticalNeighborTS[];
  contact?: boolean;
  field_reception?: boolean;
  action?: string | null;
  scenario_selected?: string | null;
  regime_id?: string;
  coverage?: 'CONTIGUOUS' | 'SPARSE' | 'GAP' | string;
  exo_without_body?: Record<string, number> | null;
  foreign_body_contribution?: Record<string, number> | null;
  foreign_body_total?: number;
  body_exposure?: boolean;
  selected_source_body_id?: string | null;
  termination_hint?: string | null;
  vision_radius?: number;
};

export type AgentVisionSummary = {
  foreign_body_exposure_ticks: NaMetric;
  observed_exposure_episodes: NaMetric;
  vision_only_episodes: NaMetric;
  peak_body_optical_contribution: NaMetric;
  exo_body_derived_delta: NaMetric | Record<string, number>;
  body_derived_exo_peaks?: Record<string, number>;
  next_action_observations: NaMetric | Record<string, number>;
  first_observed_exposure?: number | null;
  exposure_without_contact_episodes?: number;
  cognition_linkage: string;
};

/** Where optical ticks came from — LIVE_FRAME_ONLY must not invent run history. */
export type OpticalHistoryAuthority = 'HISTORICAL' | 'LIVE_FRAME_ONLY' | 'NONE';

export type VisionForensicsReport = {
  coverage: string;
  n_ticks: number;
  /** HISTORICAL = scientific_rows / contiguous series; LIVE_FRAME_ONLY = single-frame fallback. */
  optical_history_authority?: OpticalHistoryAuthority;
  events: any[];
  episodes: any[];
  causal_chains: CausalChain[];
  followup: any[];
  summary: {
    foreign_body_visual_entries: number | 'NOT_AVAILABLE';
    exposure_episodes: number | 'NOT_AVAILABLE';
    vision_only_episodes: number | 'NOT_AVAILABLE';
    exposure_without_contact_episodes: number | 'NOT_AVAILABLE';
    agents_with_optical_evidence: number;
    total_exposure_ticks: number | 'NOT_AVAILABLE';
    peak_body_contribution: number | 'NOT_AVAILABLE';
    first_observed_body_optical_exposure: null | {
      tick: number;
      wording: string;
      source_body_id?: string;
      evidence_class: EvidenceClass;
    };
    first_observed_body_visual_entry: null | {
      tick: number;
      wording: string;
      source_body_id?: string;
      evidence_class: EvidenceClass;
    };
    /** When LIVE_FRAME_ONLY, first exposure is NOT_AVAILABLE (not NONE). */
    first_observed_exposure_status?: 'OBSERVED' | 'NONE' | 'NOT_AVAILABLE';
    first_observed_contact?: number | null;
    exposure_before_contact_delta?: number | null;
    cognition_linkage_default: string;
    disclaimer: string;
    peak_body_optical?: number | 'NOT_AVAILABLE';
    by_agent?: Record<string, AgentVisionSummary>;
  };
};

const DISCLAIMER =
  'Physical visual exposure ≠ recognition. Sensor change ≠ interpretation. Temporal follow-up ≠ causal behavioral effect.';

export function counterfactualBodyContribution(
  exo: Record<string, number> | null | undefined,
  exoWithout: Record<string, number> | null | undefined,
): { contribution: Record<string, number>; total: number; body_exposure: boolean } {
  const keys = ['exo_0', 'exo_1', 'exo_2'];
  const contribution: Record<string, number> = {};
  let total = 0;
  for (const k of keys) {
    const d = Math.max(0, Number(exo?.[k] ?? 0) - Number(exoWithout?.[k] ?? 0));
    contribution[k] = d;
    total += d;
  }
  return { contribution, total, body_exposure: total > BODY_OPTICAL_EPS };
}

/**
 * BODY_OPTICAL_EXPOSURE: surviving foreign-body optical contribution to agent-accessible
 * exo after the real physical pipeline (soft-OR + FOV + distance + illumination + threshold).
 * Prefer authoritative body_exposure / foreign_body_total from vision_optical compact.
 */
export function bodyOpticalActive(t: OpticalTickTS): boolean {
  if (t.vision_enabled === false || t.body_optics_enabled === false) return false;
  if (typeof t.body_exposure === 'boolean') return t.body_exposure;
  if (typeof t.foreign_body_total === 'number') return t.foreign_body_total > BODY_OPTICAL_EPS;
  if (t.exo_without_body) {
    return counterfactualBodyContribution(t.exo, t.exo_without_body).body_exposure;
  }
  // Legacy neighbor heuristic: body_opt must survive into final_contribution inside FOV.
  return (t.neighbors || []).some(
    (n) => n.body_optical > 0 && n.inside_fov && n.final_contribution > 0,
  );
}

function peakContribution(t: OpticalTickTS): number {
  if (typeof t.foreign_body_total === 'number') return t.foreign_body_total;
  if (t.foreign_body_contribution) {
    return Object.values(t.foreign_body_contribution).reduce((a, b) => a + Number(b || 0), 0);
  }
  if (t.exo_without_body) {
    return counterfactualBodyContribution(t.exo, t.exo_without_body).total;
  }
  return Math.max(0, ...(t.neighbors || []).map((n) => (n.inside_fov ? n.body_optical : 0)));
}

function contributingSources(t: OpticalTickTS): Set<string> {
  const out = new Set<string>();
  if (!bodyOpticalActive(t)) return out;
  for (const n of t.neighbors || []) {
    if (n.body_optical > 0 && n.inside_fov && n.final_contribution > 0) {
      for (const id of n.source_body_ids || []) out.add(id);
    }
  }
  if (t.selected_source_body_id) out.add(t.selected_source_body_id);
  if (out.size === 0) out.add('foreign_body_anonymous');
  return out;
}

export function channelOverlap(t: OpticalTickTS): string {
  if (!bodyOpticalActive(t)) return 'NO_BODY_VISION';
  if (t.contact && t.field_reception) return 'VISION_PLUS_FIELD_PLUS_CONTACT';
  if (t.field_reception) return 'VISION_WITH_SIGNAL';
  if (t.contact) return 'VISION_PLUS_CONTACT';
  // Strongest conservative label when signal cannot be excluded is VISION_WITHOUT_CONTACT
  // only when field_reception is explicitly false.
  if (t.field_reception === false || t.field_reception == null) return 'VISION_WITHOUT_CONTACT';
  return 'VISION_SIGNAL_STATUS_MIXED';
}

function terminationReason(prev: OpticalTickTS | undefined, snap: OpticalTickTS): string {
  if (snap.coverage === 'GAP') return 'COVERAGE_GAP';
  if (snap.vision_enabled === false) return 'SENSOR_DISABLED';
  if (snap.body_optics_enabled === false) return 'BODY_OPTICS_DISABLED';
  if (snap.termination_hint) return String(snap.termination_hint);
  if (prev && prev.regime_id !== snap.regime_id) return 'REGIME_CHANGE';
  return 'CONTRIBUTION_LOST';
}

export function buildVisionEvents(ticks: OpticalTickTS[]): any[] {
  const events: any[] = [];
  const prevActive = new Map<string, Set<string>>();
  const prevSnap = new Map<string, OpticalTickTS>();
  const sorted = [...ticks].sort((a, b) => a.tick - b.tick);
  for (const snap of sorted) {
    if (snap.coverage === 'GAP') {
      const was = prevActive.get(snap.observer_body_id) || new Set();
      for (const sid of [...was].sort()) {
        events.push({
          type: 'BODY_OPTICAL_EXIT',
          tick: snap.tick,
          observer_body_id: snap.observer_body_id,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          evidence_class: 'OBSERVED',
          termination_reason: 'COVERAGE_GAP',
          regime_id: snap.regime_id || 'default',
        });
      }
      prevActive.set(snap.observer_body_id, new Set());
      continue;
    }
    const oid = snap.observer_body_id;
    const active = bodyOpticalActive(snap) ? contributingSources(snap) : new Set<string>();
    const was = prevActive.get(oid) || new Set();
    const prev = prevSnap.get(oid);
    for (const sid of [...active].sort()) {
      if (!was.has(sid)) {
        events.push({
          type: 'BODY_OPTICAL_ENTER',
          tick: snap.tick,
          observer_body_id: oid,
          observer_agent_id: snap.observer_agent_id,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          evidence_class: 'OBSERVED',
          channel_overlap: channelOverlap(snap),
          foreign_body_total: peakContribution(snap),
          regime_id: snap.regime_id || 'default',
        });
        // Alias for older report wording
        events.push({
          type: 'BODY_VISUAL_ENTRY',
          tick: snap.tick,
          observer_body_id: oid,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          evidence_class: 'OBSERVED',
          channel_overlap: channelOverlap(snap),
          regime_id: snap.regime_id || 'default',
        });
      }
    }
    for (const sid of [...was].sort()) {
      if (!active.has(sid)) {
        events.push({
          type: 'BODY_OPTICAL_EXIT',
          tick: snap.tick,
          observer_body_id: oid,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          evidence_class: 'OBSERVED',
          termination_reason: terminationReason(prev, snap),
          regime_id: snap.regime_id || 'default',
        });
      }
    }
    if (active.size) {
      events.push({
        type: 'BODY_OPTICAL_EXPOSURE',
        tick: snap.tick,
        observer_body_id: oid,
        source_body_ids: [...active].sort(),
        source_identity_layer: 'OBSERVER_GT_ONLY',
        evidence_class: 'OBSERVED',
        foreign_body_total: peakContribution(snap),
        peak_body_optical: Math.max(0, ...(snap.neighbors || []).map((n) => n.body_optical)),
        channel_overlap: channelOverlap(snap),
      });
      events.push({
        type: 'BODY_OPTICAL_CONTRIBUTION',
        tick: snap.tick,
        observer_body_id: oid,
        source_body_ids: [...active].sort(),
        source_identity_layer: 'OBSERVER_GT_ONLY',
        evidence_class: 'OBSERVED',
        peak_body_optical: Math.max(0, ...(snap.neighbors || []).map((n) => n.body_optical)),
        channel_overlap: channelOverlap(snap),
      });
    }
    prevActive.set(oid, active);
    prevSnap.set(oid, snap);
  }
  return events;
}

export function buildVisionEpisodes(ticks: OpticalTickTS[]): any[] {
  const episodes: any[] = [];
  const open = new Map<string, any>();
  const keyOf = (oid: string, sid: string) => `${oid}||${sid}`;
  const lastSnap = new Map<string, OpticalTickTS>();

  const close = (k: string, endTick: number, reason: string, gapBreak = false) => {
    const ep = open.get(k);
    if (!ep) return;
    open.delete(k);
    ep.end_tick = endTick;
    ep.observed_duration = endTick - ep.start_tick + 1;
    ep.observed_contiguous_duration = ep.observed_duration;
    ep.termination_reason = reason;
    if (ep.had_gap || gapBreak) {
      ep.true_duration = 'NOT_AVAILABLE';
      ep.coverage_status = 'SPARSE';
    } else {
      ep.true_duration = ep.observed_duration;
      ep.coverage_status = 'CONTIGUOUS';
    }
    ep.peak_foreign_body_contribution = Math.max(0, ...(ep._peaks || [0]));
    ep.peak_body_optical = ep.peak_foreign_body_contribution;
    delete ep._peaks;
    ep.channel_overlaps = [...(ep.channel_overlap_set || [])].sort();
    delete ep.channel_overlap_set;
    const overlaps = ep.channel_overlaps as string[];
    ep.vision_only =
      overlaps.length === 1
      && (overlaps[0] === 'VISION_WITHOUT_CONTACT' || overlaps[0] === 'VISION_ONLY');
    ep.vision_without_contact = ep.vision_only;
    ep.contact_overlap = overlaps.some((o) => o.includes('CONTACT'));
    ep.signal_overlap = overlaps.some((o) => o.includes('SIGNAL') || o.includes('FIELD'));
    episodes.push(ep);
  };

  const sorted = [...ticks].sort(
    (a, b) => a.tick - b.tick || a.observer_body_id.localeCompare(b.observer_body_id),
  );
  for (const snap of sorted) {
    const oid = snap.observer_body_id;
    lastSnap.set(oid, snap);
    if (snap.coverage === 'GAP') {
      for (const k of [...open.keys()]) {
        if (k.startsWith(`${oid}||`)) close(k, snap.tick - 1, 'COVERAGE_GAP', true);
      }
      continue;
    }
    const active = bodyOpticalActive(snap) ? contributingSources(snap) : new Set<string>();
    for (const k of [...open.keys()]) {
      if (!k.startsWith(`${oid}||`)) continue;
      const sid = k.slice(oid.length + 2);
      if (!active.has(sid)) close(k, snap.tick - 1, terminationReason(undefined, snap));
    }
    for (const sid of active) {
      const k = keyOf(oid, sid);
      if (!open.has(k)) {
        open.set(k, {
          type: 'VISUAL_EXPOSURE_EPISODE',
          observer_body_id: oid,
          observer_agent_id: snap.observer_agent_id,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          start_tick: snap.tick,
          regime_id: snap.regime_id || 'default',
          channel_overlap_set: new Set<string>(),
          _peaks: [] as number[],
          had_gap: false,
        });
      }
      const ep = open.get(k)!;
      if (ep.regime_id !== (snap.regime_id || 'default')) {
        close(k, snap.tick - 1, 'REGIME_CHANGE');
        open.set(k, {
          type: 'VISUAL_EXPOSURE_EPISODE',
          observer_body_id: oid,
          observer_agent_id: snap.observer_agent_id,
          source_body_id: sid,
          source_identity_layer: 'OBSERVER_GT_ONLY',
          start_tick: snap.tick,
          regime_id: snap.regime_id || 'default',
          channel_overlap_set: new Set<string>(),
          _peaks: [] as number[],
          had_gap: false,
        });
      }
      const cur = open.get(k)!;
      cur.channel_overlap_set.add(channelOverlap(snap));
      cur._peaks.push(peakContribution(snap));
      if (snap.coverage === 'SPARSE') cur.had_gap = true;
    }
  }
  for (const k of [...open.keys()]) {
    const oid = k.split('||')[0];
    const last = lastSnap.get(oid);
    close(k, last?.tick ?? open.get(k).start_tick, last ? 'RUN_END' : 'RUN_END');
  }
  return episodes;
}

export function buildVisionCausalChains(ticks: OpticalTickTS[], maxChains = 12): CausalChain[] {
  const chains: CausalChain[] = [];
  for (const snap of ticks) {
    if (snap.coverage === 'GAP' || !bodyOpticalActive(snap)) continue;
    const sources = contributingSources(snap);
    for (const sid of [...sources].sort()) {
      const cells = (snap.neighbors || []).filter((n) => n.body_optical > 0 && n.inside_fov);
      const peak = cells.length
        ? cells.reduce((a, b) => (a.final_contribution >= b.final_contribution ? a : b))
        : null;
      chains.push({
        id: `chain-vision-${snap.tick}-${sid}-${snap.observer_body_id}`,
        tick: snap.tick,
        nodes: [
          `body_footprint:${sid}`,
          peak ? `body_opt:cell${JSON.stringify(peak.cell)}` : 'body_opt',
          'composed_optical_source',
          'physical_sensor_contribution',
          'exo_*',
          'later_cognition_or_action',
        ],
        edges: [
          {
            from: `body_footprint:${sid}`,
            to: peak ? `body_opt:cell${JSON.stringify(peak.cell)}` : 'body_opt',
            link: 'DIRECT_CAUSAL_LINK',
            reason: 'Foreign footprint occupancy maps to body_opt via max optical_response.',
          },
          {
            from: peak ? `body_opt:cell${JSON.stringify(peak.cell)}` : 'body_opt',
            to: 'composed_optical_source',
            link: 'DIRECT_CAUSAL_LINK',
            reason: 'composed = 1-(1-surf)*(1-body_opt) (validated soft-OR).',
          },
          {
            from: 'composed_optical_source',
            to: 'physical_sensor_contribution',
            link: 'DIRECT_CAUSAL_LINK',
            reason: 'Same illumination × FOV × angular × distance filter as surface.',
          },
          {
            from: 'physical_sensor_contribution',
            to: 'exo_*',
            link: 'DIRECT_CAUSAL_LINK',
            reason: 'Channel bins accumulate final_contribution into exo_0/1/2.',
          },
          {
            from: 'exo_*',
            to: 'later_cognition_or_action',
            link: 'NOT_ESTABLISHED',
            reason: 'No causal_parent_ids from exo to scenario/action in runtime provenance.',
          },
        ],
      });
      if (chains.length >= maxChains) return chains;
    }
  }
  return chains;
}

function nextActionObservations(
  ticks: OpticalTickTS[],
  episodes: any[],
): Record<string, Record<string, number>> {
  const byAgent: Record<string, Record<string, number>> = {};
  const byObs = new Map<string, OpticalTickTS[]>();
  for (const t of ticks) {
    const aid = t.observer_agent_id || t.observer_body_id;
    if (!byObs.has(aid)) byObs.set(aid, []);
    byObs.get(aid)!.push(t);
  }
  for (const [, series] of byObs) {
    series.sort((a, b) => a.tick - b.tick);
  }
  for (const ep of episodes) {
    const aid = ep.observer_agent_id || ep.observer_body_id;
    const series = byObs.get(aid) || [];
    const next = series.find((t) => t.tick > ep.start_tick) || series.find((t) => t.tick === ep.start_tick);
    const action = String(next?.action || 'UNKNOWN');
    const bucket = action.startsWith('MOVE') ? 'MOVE' : action === 'WAIT' ? 'WAIT' : action;
    if (!byAgent[aid]) byAgent[aid] = {};
    byAgent[aid][bucket] = (byAgent[aid][bucket] || 0) + 1;
    ep.next_action = action;
    ep.next_action_tick = next?.tick ?? null;
    ep.next_action_class = 'TEMPORALLY_ASSOCIATED';
  }
  return byAgent;
}

export function analyzeOpticalSeries(
  ticks: OpticalTickTS[],
  opts?: {
    first_contact_tick?: number | null;
    /** LIVE_FRAME_ONLY: do not present single-frame counts as run history. */
    optical_history_authority?: OpticalHistoryAuthority;
  },
): VisionForensicsReport {
  const authority: OpticalHistoryAuthority =
    opts?.optical_history_authority
    ?? (ticks.length ? 'HISTORICAL' : 'NONE');

  if (!ticks.length) {
    return {
      coverage: 'NOT_AVAILABLE',
      n_ticks: 0,
      optical_history_authority: 'NONE',
      events: [],
      episodes: [],
      causal_chains: [],
      followup: [],
      summary: {
        foreign_body_visual_entries: 'NOT_AVAILABLE',
        exposure_episodes: 'NOT_AVAILABLE',
        vision_only_episodes: 'NOT_AVAILABLE',
        exposure_without_contact_episodes: 'NOT_AVAILABLE',
        agents_with_optical_evidence: 0,
        total_exposure_ticks: 'NOT_AVAILABLE',
        peak_body_contribution: 'NOT_AVAILABLE',
        first_observed_body_optical_exposure: null,
        first_observed_body_visual_entry: null,
        first_observed_exposure_status: 'NOT_AVAILABLE',
        cognition_linkage_default: 'NOT_ESTABLISHED',
        disclaimer: DISCLAIMER,
        peak_body_optical: 'NOT_AVAILABLE',
      },
    };
  }
  const events = buildVisionEvents(ticks);
  const episodes = buildVisionEpisodes(ticks);
  const causal_chains = buildVisionCausalChains(ticks);
  const nextActs = nextActionObservations(ticks, episodes);
  const entries = events.filter((e) => e.type === 'BODY_OPTICAL_ENTER' || e.type === 'BODY_VISUAL_ENTRY');
  const uniqueEntries = events.filter((e) => e.type === 'BODY_OPTICAL_ENTER');
  const visionOnly = episodes.filter((e) => e.vision_only || e.vision_without_contact);
  const sparse = ticks.some((t) => t.coverage === 'SPARSE' || t.coverage === 'GAP');
  const peak = Math.max(0, ...ticks.map((t) => peakContribution(t)));
  const by_agent: Record<string, AgentVisionSummary> = {};
  const agentIds = new Set<string>();

  for (const t of ticks) {
    const aid = t.observer_agent_id || t.observer_body_id;
    agentIds.add(aid);
    if (!by_agent[aid]) {
      by_agent[aid] = {
        foreign_body_exposure_ticks: 0,
        observed_exposure_episodes: 0,
        vision_only_episodes: 0,
        peak_body_optical_contribution: 0,
        exo_body_derived_delta: { exo_0: 0, exo_1: 0, exo_2: 0 },
        body_derived_exo_peaks: { exo_0: 0, exo_1: 0, exo_2: 0 },
        next_action_observations: {},
        first_observed_exposure: null,
        exposure_without_contact_episodes: 0,
        cognition_linkage: 'NOT_ESTABLISHED',
      };
    }
    if (bodyOpticalActive(t)) {
      by_agent[aid].foreign_body_exposure_ticks =
        Number(by_agent[aid].foreign_body_exposure_ticks) + 1;
      const pc = peakContribution(t);
      by_agent[aid].peak_body_optical_contribution = Math.max(
        Number(by_agent[aid].peak_body_optical_contribution) || 0,
        pc,
      );
      const contrib =
        t.foreign_body_contribution
        || counterfactualBodyContribution(t.exo, t.exo_without_body).contribution;
      const peaks = by_agent[aid].body_derived_exo_peaks!;
      for (const k of ['exo_0', 'exo_1', 'exo_2']) {
        peaks[k] = Math.max(peaks[k] || 0, Number(contrib[k] || 0));
      }
      by_agent[aid].exo_body_derived_delta = { ...peaks };
      if (by_agent[aid].first_observed_exposure == null) {
        by_agent[aid].first_observed_exposure = t.tick;
      }
    }
  }
  for (const ep of episodes) {
    const aid = ep.observer_agent_id || ep.observer_body_id;
    if (!by_agent[aid]) continue;
    by_agent[aid].observed_exposure_episodes =
      Number(by_agent[aid].observed_exposure_episodes) + 1;
    if (ep.vision_only || ep.vision_without_contact) {
      by_agent[aid].vision_only_episodes = Number(by_agent[aid].vision_only_episodes) + 1;
      by_agent[aid].exposure_without_contact_episodes =
        Number(by_agent[aid].exposure_without_contact_episodes || 0) + 1;
    }
  }
  for (const [aid, counts] of Object.entries(nextActs)) {
    if (by_agent[aid]) by_agent[aid].next_action_observations = counts;
  }

  // Live-frame-only: never present single-tick counts as run-level history.
  if (authority === 'LIVE_FRAME_ONLY') {
    for (const aid of Object.keys(by_agent)) {
      by_agent[aid] = {
        ...by_agent[aid],
        foreign_body_exposure_ticks: 'NOT AVAILABLE',
        observed_exposure_episodes: 'NOT AVAILABLE',
        vision_only_episodes: 'NOT AVAILABLE',
        peak_body_optical_contribution: 'NOT AVAILABLE',
        first_observed_exposure: null,
        exposure_without_contact_episodes: undefined,
        next_action_observations: 'NOT AVAILABLE',
      };
    }
    return {
      coverage: 'SPARSE',
      n_ticks: ticks.length,
      optical_history_authority: 'LIVE_FRAME_ONLY',
      events: [],
      episodes: [],
      causal_chains: [],
      followup: [],
      summary: {
        foreign_body_visual_entries: 'NOT_AVAILABLE',
        exposure_episodes: 'NOT_AVAILABLE',
        vision_only_episodes: 'NOT_AVAILABLE',
        exposure_without_contact_episodes: 'NOT_AVAILABLE',
        agents_with_optical_evidence: agentIds.size,
        total_exposure_ticks: 'NOT_AVAILABLE',
        peak_body_contribution: 'NOT_AVAILABLE',
        first_observed_body_optical_exposure: null,
        first_observed_body_visual_entry: null,
        first_observed_exposure_status: 'NOT_AVAILABLE',
        first_observed_contact: opts?.first_contact_tick ?? null,
        exposure_before_contact_delta: null,
        cognition_linkage_default: 'NOT_ESTABLISHED',
        disclaimer: DISCLAIMER,
        peak_body_optical: 'NOT_AVAILABLE',
        by_agent,
      },
    };
  }

  const firstEnter = uniqueEntries[0] || entries[0] || null;
  const firstContact = opts?.first_contact_tick ?? null;
  const firstExposureTick = firstEnter?.tick ?? null;
  let exposureBeforeContact: number | null = null;
  if (firstExposureTick != null && firstContact != null) {
    exposureBeforeContact = Number(firstContact) - Number(firstExposureTick);
  }

  const totalExposureTicks = Object.values(by_agent).reduce(
    (s, a) => s + Number(a.foreign_body_exposure_ticks || 0),
    0,
  );

  return {
    coverage: sparse ? 'SPARSE' : 'CONTIGUOUS',
    n_ticks: ticks.length,
    optical_history_authority: 'HISTORICAL',
    events,
    episodes,
    causal_chains,
    followup: [],
    summary: {
      foreign_body_visual_entries: uniqueEntries.length || entries.length,
      exposure_episodes: episodes.length,
      vision_only_episodes: visionOnly.length,
      exposure_without_contact_episodes: visionOnly.length,
      agents_with_optical_evidence: agentIds.size,
      total_exposure_ticks: totalExposureTicks,
      peak_body_contribution: peak,
      first_observed_body_optical_exposure: firstEnter
        ? {
            tick: firstEnter.tick,
            wording: sparse ? 'FIRST_OBSERVED' : 'FIRST_OBSERVED',
            source_body_id: firstEnter.source_body_id,
            evidence_class: 'OBSERVED',
          }
        : null,
      first_observed_body_visual_entry: firstEnter
        ? {
            tick: firstEnter.tick,
            wording: 'FIRST OBSERVED',
            source_body_id: firstEnter.source_body_id,
            evidence_class: 'OBSERVED',
          }
        : null,
      first_observed_exposure_status: firstEnter ? 'OBSERVED' : 'NONE',
      first_observed_contact: firstContact,
      exposure_before_contact_delta: exposureBeforeContact,
      cognition_linkage_default: 'NOT_ESTABLISHED',
      disclaimer: DISCLAIMER,
      peak_body_optical: peak,
      by_agent,
    },
  };
}

/** Extract optical ticks from scientific timeline rows (vision_optical compact). */
export function opticalTicksFromScientificRows(rows: any[]): OpticalTickTS[] {
  const out: OpticalTickTS[] = [];
  for (const row of rows || []) {
    const vo = row.vision_optical;
    if (!vo || !vo.available) continue;
    const srcMap = new Map<string, string[]>();
    for (const sb of vo.source_bodies_gt || []) {
      const cell = sb.cell || [0, 0];
      const key = `${cell[0]},${cell[1]}`;
      const arr = srcMap.get(key) || [];
      arr.push(String(sb.source_body_id));
      srcMap.set(key, arr);
    }
    const exo = { ...(vo.final_exo || vo.exo || {}) };
    const exoWithout = vo.exo_without_foreign_bodies || null;
    const contrib =
      vo.foreign_body_contribution
      || (exoWithout ? counterfactualBodyContribution(exo, exoWithout).contribution : null);
    const total =
      typeof vo.foreign_body_total === 'number'
        ? vo.foreign_body_total
        : contrib
          ? Object.values(contrib).reduce((a, b) => a + Number(b || 0), 0)
          : undefined;
    const bodyExposure =
      typeof vo.body_exposure === 'boolean'
        ? vo.body_exposure
        : total != null
          ? total > BODY_OPTICAL_EPS
          : undefined;
    const visionRadius = Number(vo.vision_radius ?? vo.radius ?? 1);
    const baseRegime = String(row.regime_id || 'default');
    out.push({
      tick: Number(row.tick || 0),
      observer_body_id: String(row.body_id || 'body-0'),
      observer_agent_id: String(row.agent_id || ''),
      theta: Number(row.theta || 0),
      exo,
      illumination: Number(vo.illumination || 0),
      vision_enabled:
        vo.vision_enabled !== false
        && vo.perception_enabled !== false
        && vo.vision_contributes !== false,
      body_optics_enabled:
        vo.body_optics_enabled !== false && vo.body_optical_enabled !== false,
      neighbors: (vo.neighbors_optical || []).map((n: any) => {
        const cell = n.cell || [0, 0];
        return {
          cell,
          inside_fov: !!n.inside_fov,
          surface_response: Number(n.surface_response || 0),
          body_optical: Number(n.body_optical || 0),
          composed_optical: Number(n.composed_optical || 0),
          final_contribution: Number(n.final_contribution || 0),
          relative_angle_deg: Number(n.relative_angle_deg || 0),
          distance: n.distance != null ? Number(n.distance) : undefined,
          detectable: n.detectable,
          source_body_ids: srcMap.get(`${cell[0]},${cell[1]}`) || [],
        };
      }),
      contact: !!row.contact,
      field_reception: !!vo.field_reception,
      action: row.action ?? null,
      coverage: row.coverage || 'CONTIGUOUS',
      regime_id: `${baseRegime}|vision_R${visionRadius}`,
      vision_radius: visionRadius,
      exo_without_body: exoWithout,
      foreign_body_contribution: contrib,
      foreign_body_total: total,
      body_exposure: bodyExposure,
      selected_source_body_id: vo.source_bodies_gt?.[0]?.source_body_id ?? null,
    });
  }
  return out;
}

/** LIVE frame near_field_exteroception → optical tick (same authority; may be sparse). */
export function opticalTickFromLiveFrame(frame: any, agentId = 'agent_0'): OpticalTickTS | null {
  const view = frame?.agents_views?.[agentId] || frame;
  const nf =
    view?.physical?.near_field_exteroception
    || frame?.physical?.near_field_exteroception
    || frame?.perception?.near_field_exteroception;
  if (!nf) return null;
  // Compact peer stubs omit neighbors — still usable if fragments / body cell counts exist.
  const neighbors = (nf.neighbors || [])
    .filter((n: any) => Number(n.body_optical || 0) > 0 || Number(n.final_contribution || 0) > 0)
    .map((n: any) => ({
      cell: n.cell || [0, 0],
      inside_fov: !!n.inside_fov,
      surface_response: Number(n.surface_response || 0),
      body_optical: Number(n.body_optical || 0),
      composed_optical: Number(n.composed_optical || n.surface_response || 0),
      final_contribution: Number(n.final_contribution || 0),
      relative_angle_deg: Number(n.relative_angle_deg || 0),
      distance: n.distance != null ? Number(n.distance) : undefined,
      detectable: n.detectable,
      source_body_ids: [] as string[],
    }));
  if (!neighbors.length && nf.fragments == null && nf.n_body_optical_cells == null) return null;
  const exo = { ...(nf.fragments || {}) };
  // LIVE frame alone lacks exo_without — exposure only if body optical cells present
  // with surviving final_contribution (or authoritative body_exposure if present).
  let bodyExposure: boolean | undefined = nf.body_exposure;
  let foreignTotal: number | undefined = nf.foreign_body_total;
  if (bodyExposure == null) {
    bodyExposure = neighbors.some(
      (n: OpticalNeighborTS) => n.body_optical > 0 && n.inside_fov && n.final_contribution > 0,
    );
    if (!neighbors.length && Number(nf.n_body_optical_cells || 0) > 0) {
      // Stub without neighbors: cannot prove surviving contribution → not exposure.
      bodyExposure = false;
    }
  }
  return {
    tick: Number(frame?.header?.tick ?? frame?.overview_facts?.tick ?? nf.tick ?? 0),
    observer_body_id: String(
      view?.body_id || `body-${String(agentId).replace('agent_', '').replace('undercover', 'uc')}`,
    ),
    observer_agent_id: agentId,
    theta: Number(nf.body_theta || 0),
    exo,
    illumination: Number(nf.illumination || 0),
    vision_enabled: nf.perception_enabled !== false && nf.vision_contributes !== false,
    body_optics_enabled: nf.body_optical_enabled !== false,
    neighbors,
    contact: !!frame?.contact?.contact,
    field_reception: false,
    action: view?.physical?.selected_action ?? frame?.physical?.selected_action ?? null,
    coverage: 'SPARSE',
    regime_id: `live|vision_R${Math.max(1, Math.min(3, Number(nf.vision_radius ?? nf.radius ?? 1)))}`,
    vision_radius: Math.max(1, Math.min(3, Number(nf.vision_radius ?? nf.radius ?? 1))),
    body_exposure: bodyExposure,
    foreign_body_total: foreignTotal,
  };
}

export function visionImportantEvents(report: VisionForensicsReport): ImportantEvent[] {
  const out: ImportantEvent[] = [];
  if (report.optical_history_authority === 'LIVE_FRAME_ONLY' || report.optical_history_authority === 'NONE') {
    return out;
  }
  const fe =
    report.summary.first_observed_body_optical_exposure
    || report.summary.first_observed_body_visual_entry;
  if (fe) {
    out.push({
      tick: fe.tick,
      category: 'FIRST',
      kind: 'FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE',
      title: 'FIRST OBSERVED BODY OPTICAL EXPOSURE',
      reason:
        `Foreign-body optical contribution survived the physical sensor pipeline (GT source=${fe.source_body_id}). `
        + 'Not recognition. Coverage may be incomplete under sparse LIVE sampling.',
      evidence_class: 'OBSERVED',
      body_ids: fe.source_body_id ? [fe.source_body_id] : undefined,
    });
  }
  if (
    report.summary.first_observed_contact != null
    && report.summary.exposure_before_contact_delta != null
    && report.summary.exposure_before_contact_delta > 0
  ) {
    out.push({
      tick: fe?.tick ?? 0,
      category: 'FIRST',
      kind: 'EXPOSURE_BEFORE_CONTACT',
      title: 'FOREIGN-BODY OPTICAL EXPOSURE BEFORE CONTACT',
      reason:
        `Foreign-body optical contribution was observed ${report.summary.exposure_before_contact_delta} `
        + `ticks before first body-body contact (t${report.summary.first_observed_contact}). `
        + 'Observational only — not approach/recognition.',
      evidence_class: 'OBSERVED',
    });
  }
  const visionOnly = report.episodes.find((e) => e.vision_only || e.vision_without_contact);
  if (visionOnly) {
    out.push({
      tick: visionOnly.start_tick,
      category: 'FIRST',
      kind: 'FIRST_OBSERVED_VISION_WITHOUT_CONTACT',
      title: 'FIRST OBSERVED VISION WITHOUT CONTACT',
      reason: 'Exposure episode classified VISION_WITHOUT_CONTACT (no concurrent contact in series).',
      evidence_class: 'OBSERVED',
    });
  }
  return out;
}

export function formatVisualForensicsSection(report: VisionForensicsReport | null | undefined): string[] {
  const lines: string[] = [];
  lines.push('VISUAL FORENSICS');
  lines.push('  Physical visual exposure ≠ recognition.');
  lines.push('  Sensor change ≠ interpretation.');
  lines.push('  Temporal follow-up ≠ causal behavioral effect.');
  if (!report || report.coverage === 'NOT_AVAILABLE' || report.optical_history_authority === 'NONE') {
    lines.push('  Coverage: NOT_AVAILABLE (no vision_optical / near_field optical series supplied)');
    lines.push('  Cognition linkage: NOT_ESTABLISHED');
    return lines;
  }
  const s = report.summary;
  if (report.optical_history_authority === 'LIVE_FRAME_ONLY') {
    lines.push('  Coverage: SPARSE (live-frame fallback — not run history)');
    lines.push(`  Agents with optical evidence (current frame): ${s.agents_with_optical_evidence}`);
    lines.push('  Total exposure ticks: NOT_AVAILABLE');
    lines.push('  Exposure episodes: NOT_AVAILABLE');
    lines.push('  Peak body contribution: NOT_AVAILABLE');
    lines.push('  FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: NOT_AVAILABLE');
    lines.push('  Cognition linkage: NOT_ESTABLISHED');
    lines.push('  Note: Analyze Current requires scientific_timeline evidence for historical Visual Forensics.');
    return lines;
  }
  lines.push(`  Coverage: ${report.coverage}`);
  lines.push(`  Agents with optical evidence: ${s.agents_with_optical_evidence}`);
  lines.push(`  Total exposure ticks: ${s.total_exposure_ticks}`);
  lines.push(`  Exposure episodes: ${s.exposure_episodes}`);
  lines.push(`  Exposure without contact: ${s.exposure_without_contact_episodes}`);
  lines.push(`  Peak body contribution: ${s.peak_body_contribution ?? s.peak_body_optical ?? 'NOT_AVAILABLE'}`);
  const radii = new Set(
    (report.episodes || [])
      .map((e: any) => String(e.regime_id || ''))
      .filter((r: string) => r.includes('vision_R'))
      .map((r: string) => r.replace(/^.*vision_R/, 'R')),
  );
  if (radii.size) {
    lines.push(`  Vision-radius regimes observed: ${[...radii].sort().join(', ')}`);
  }
  if (s.first_observed_exposure_status === 'NOT_AVAILABLE') {
    lines.push('  FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: NOT_AVAILABLE');
  } else if (s.first_observed_body_optical_exposure) {
    const fe = s.first_observed_body_optical_exposure;
    lines.push(
      `  FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: t${fe.tick} (source GT=${fe.source_body_id})`,
    );
  } else {
    lines.push('  FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: NONE');
  }
  if (s.first_observed_contact != null && s.exposure_before_contact_delta != null) {
    lines.push(`  FIRST_OBSERVED_CONTACT: t${s.first_observed_contact}`);
    lines.push(`  exposure→contact delta: ${s.exposure_before_contact_delta} ticks`);
  }
  lines.push(`  Cognition linkage: ${s.cognition_linkage_default}`);
  lines.push('  Visual causal chains (representative):');
  if (!report.causal_chains.length) lines.push('    NONE / NOT_AVAILABLE');
  for (const ch of report.causal_chains.slice(0, 8)) {
    lines.push(`    ${ch.id} @ t${ch.tick}`);
    for (const e of ch.edges) {
      lines.push(`      ${e.from} =[${e.link}]=> ${e.to}`);
    }
  }
  return lines;
}

export function mergeAgentVision(
  agent: AgentAnalysis,
  summary: AgentVisionSummary | undefined,
): AgentAnalysis {
  if (!summary) {
    return {
      ...agent,
      vision: {
        foreign_body_exposure_ticks: 'NOT AVAILABLE',
        observed_exposure_episodes: 'NOT AVAILABLE',
        vision_only_episodes: 'NOT AVAILABLE',
        peak_body_optical_contribution: 'NOT AVAILABLE',
        exo_body_derived_delta: 'NOT AVAILABLE',
        next_action_observations: 'NOT AVAILABLE',
        cognition_linkage: 'NOT_ESTABLISHED',
      },
    };
  }
  return { ...agent, vision: summary };
}

/** No-op when AnalysisState has no optical series — keeps signal forensics unchanged. */
export function visionForensicsFromState(
  _state: AnalysisState,
  opticalTicks?: OpticalTickTS[],
): VisionForensicsReport {
  return analyzeOpticalSeries(opticalTicks || []);
}
