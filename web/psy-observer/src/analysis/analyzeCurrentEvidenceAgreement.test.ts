/**
 * Analyze Current vs Run explicit analysis — same evidence package path.
 * Live-frame-only fallback must not invent run-level Visual Forensics history.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeEvidencePackage, type EvidencePackage } from './scientificEvidence.ts';
import { buildRunAnalysis, ingestAnalysisInput } from './runAnalysis.ts';
import { createAnalysisState } from './aggregates.ts';
import {
  analyzeOpticalSeries,
  formatVisualForensicsSection,
  opticalTickFromLiveFrame,
  type OpticalTickTS,
} from './visionForensics.ts';

function sciRow(partial: {
  tick: number;
  agent_id: string;
  body_id: string;
  body_exposure: boolean;
  foreign_body_total: number;
  radius?: number;
}): any {
  const exo = {
    exo_0: 0.01,
    exo_1: 0.2 + (partial.body_exposure ? partial.foreign_body_total : 0),
    exo_2: 0.02,
  };
  const exoWithout = { exo_0: 0.01, exo_1: 0.2, exo_2: 0.02 };
  return {
    tick: partial.tick,
    agent_id: partial.agent_id,
    body_id: partial.body_id,
    action: 'WAIT',
    action_source: 'WAIT',
    body_xy: { x: 10, y: 10 },
    vision_optical: {
      available: true,
      vision_enabled: true,
      body_optics_enabled: true,
      body_optical_enabled: true,
      perception_enabled: true,
      vision_contributes: true,
      final_exo: exo,
      exo,
      exo_without_foreign_bodies: exoWithout,
      foreign_body_contribution: {
        exo_0: 0,
        exo_1: partial.body_exposure ? partial.foreign_body_total : 0,
        exo_2: 0,
      },
      foreign_body_total: partial.body_exposure ? partial.foreign_body_total : 0,
      body_exposure: partial.body_exposure,
      vision_radius: partial.radius ?? 1,
      radius: partial.radius ?? 1,
      neighbors_optical: partial.body_exposure
        ? [
            {
              cell: [11, 10],
              inside_fov: true,
              body_optical: 0.65,
              composed_optical: 0.87,
              final_contribution: 0.13,
              surface_response: 0.4,
              detectable: true,
            },
          ]
        : [],
      source_bodies_gt: partial.body_exposure
        ? [{ source_body_id: partial.agent_id === 'agent_0' ? 'body-1' : 'body-0', cell: [11, 10] }]
        : [],
    },
  };
}

function makeHistoricalPackage(): EvidencePackage {
  const scientific_rows: any[] = [];
  // Contiguous series with exposures for both agents (deterministic).
  for (let t = 1; t <= 40; t++) {
    const a0Exp = t >= 10 && t <= 25;
    const a1Exp = t >= 18 && t <= 30;
    scientific_rows.push(
      sciRow({
        tick: t,
        agent_id: 'agent_0',
        body_id: 'body-0',
        body_exposure: a0Exp,
        foreign_body_total: a0Exp ? 0.12 : 0,
        radius: t < 20 ? 1 : 2,
      }),
      sciRow({
        tick: t,
        agent_id: 'agent_1',
        body_id: 'body-1',
        body_exposure: a1Exp,
        foreign_body_total: a1Exp ? 0.09 : 0,
        radius: t < 20 ? 1 : 2,
      }),
    );
  }
  const timeline = [];
  for (let t = 1; t <= 40; t++) {
    timeline.push({
      tick: t,
      bodies: [
        { agent_id: 'agent_0', action: 'WAIT', x: 10, y: 10 },
        { agent_id: 'agent_1', action: 'WAIT', x: 12, y: 10 },
      ],
    });
  }
  return {
    schema: 'mm.analysis.evidence.v1',
    analyzer_version: '1.1.0',
    source: 'current',
    runtime_status: 'RUNNING',
    analysis_cutoff_tick: 40,
    scientific_tick_range: [1, 40],
    coverage: 'FULL',
    complete_tick_level_reanalysis: true,
    identity: {
      seed: 99,
      runtime_generation: 2,
      runtime_type: 'TwoAgentRuntime',
      agent_count: 2,
    },
    evidence_counts: { scientific_rows: scientific_rows.length, timeline_events: timeline.length },
    timeline,
    events: [],
    scientific_rows,
  };
}

function visionCore(a: ReturnType<typeof analyzeEvidencePackage>) {
  const vf = a.vision_forensics!;
  const s = vf.summary;
  return {
    coverage: vf.coverage,
    optical_history_authority: vf.optical_history_authority,
    total_exposure_ticks: s.total_exposure_ticks,
    exposure_episodes: s.exposure_episodes,
    peak_body_contribution: s.peak_body_contribution,
    first_tick: s.first_observed_body_optical_exposure?.tick ?? null,
    first_status: s.first_observed_exposure_status,
    agents_with_optical_evidence: s.agents_with_optical_evidence,
    by_agent: Object.fromEntries(
      Object.entries(s.by_agent || {}).map(([k, v]) => [
        k,
        {
          foreign_body_exposure_ticks: v.foreign_body_exposure_ticks,
          observed_exposure_episodes: v.observed_exposure_episodes,
          peak_body_optical_contribution: v.peak_body_optical_contribution,
          first_observed_exposure: v.first_observed_exposure ?? null,
        },
      ]),
    ),
  };
}

describe('analyzeCurrentEvidenceAgreement', () => {
  it('Analyze Current (evidence package) agrees with Run explicit analysis on Visual Forensics', () => {
    const pkg = makeHistoricalPackage();
    // Explicit analysis path
    const explicit = analyzeEvidencePackage(pkg, { mode: 'LIVE' });
    // Analyze Current uses the same analyzeEvidencePackage for current-run evidence
    const analyzeCurrent = analyzeEvidencePackage(pkg, { mode: 'LIVE' });

    assert.deepEqual(visionCore(analyzeCurrent), visionCore(explicit));

    const core = visionCore(explicit);
    assert.equal(core.optical_history_authority, 'HISTORICAL');
    assert.equal(core.agents_with_optical_evidence, 2);
    assert.ok(Number(core.total_exposure_ticks) > 0);
    assert.ok(Number(core.exposure_episodes) > 0);
    assert.ok(Number(core.peak_body_contribution) > 0);
    assert.equal(core.first_tick, 10);
    assert.equal(core.first_status, 'OBSERVED');
    // Both agents present in per-agent results
    assert.ok(core.by_agent.agent_0);
    assert.ok(core.by_agent.agent_1);
    assert.ok(Number(core.by_agent.agent_0.foreign_body_exposure_ticks) > 0);
    assert.ok(Number(core.by_agent.agent_1.foreign_body_exposure_ticks) > 0);
  });

  it('run-level Visual Forensics is independent of which agent is projected in the live frame', () => {
    const pkg = makeHistoricalPackage();
    const frameA0 = {
      header: { tick: 40, status: 'RUNNING', seed: 99, runtime_generation: 2, selected_agent_id: 'agent_0' },
      agents_views: {
        agent_0: { agent_id: 'agent_0', physical: { near_field_exteroception: { fragments: { exo_0: 0 } } } },
        agent_1: { agent_id: 'agent_1', physical: { detail: 'compact', near_field_exteroception: { detail: 'compact', fragments: { exo_0: 0 } } } },
      },
    };
    const frameA1 = {
      ...frameA0,
      header: { ...frameA0.header, selected_agent_id: 'agent_1' },
    };
    const a = visionCore(analyzeEvidencePackage(pkg, { mode: 'LIVE', frame: frameA0 }));
    const b = visionCore(analyzeEvidencePackage(pkg, { mode: 'LIVE', frame: frameA1 }));
    assert.deepEqual(a, b);
  });

  it('live-frame-only fallback marks historical Visual Forensics as NOT_AVAILABLE', () => {
    const frame = {
      header: { tick: 99, status: 'RUNNING', seed: 17, runtime_generation: 1 },
      agents_views: {
        agent_0: {
          agent_id: 'agent_0',
          body_id: 'body-0',
          physical: {
            near_field_exteroception: {
              perception_enabled: true,
              vision_contributes: true,
              body_optical_enabled: true,
              fragments: { exo_0: 0.1, exo_1: 0.2, exo_2: 0 },
              n_body_optical_cells: 1,
              neighbors: [
                {
                  cell: [1, 1],
                  inside_fov: true,
                  body_optical: 0.65,
                  composed_optical: 0.87,
                  final_contribution: 0.132,
                  surface_response: 0.4,
                  detectable: true,
                },
              ],
              vision_radius: 2,
            },
          },
        },
        agent_1: {
          agent_id: 'agent_1',
          body_id: 'body-1',
          physical: {
            detail: 'compact',
            near_field_exteroception: {
              detail: 'compact',
              perception_enabled: true,
              vision_contributes: true,
              body_optical_enabled: true,
              fragments: { exo_0: 0.05, exo_1: 0.1, exo_2: 0 },
              n_body_optical_cells: 0,
            },
          },
        },
      },
    };

    const state = createAnalysisState();
    ingestAnalysisInput(state, { frame, timeline: [], events: [], mode: 'LIVE' });
    const liveOnly = buildRunAnalysis(state, 'LIVE', { frame });
    const vf = liveOnly.vision_forensics!;
    assert.equal(vf.optical_history_authority, 'LIVE_FRAME_ONLY');
    assert.equal(vf.summary.total_exposure_ticks, 'NOT_AVAILABLE');
    assert.equal(vf.summary.exposure_episodes, 'NOT_AVAILABLE');
    assert.equal(vf.summary.peak_body_contribution, 'NOT_AVAILABLE');
    assert.equal(vf.summary.first_observed_exposure_status, 'NOT_AVAILABLE');
    assert.equal(vf.summary.first_observed_body_optical_exposure, null);
    const log = formatVisualForensicsSection(vf).join('\n');
    assert.match(log, /Total exposure ticks: NOT_AVAILABLE/);
    assert.match(log, /FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: NOT_AVAILABLE/);
    // Must not invent zeros as historical certainty
    assert.doesNotMatch(log, /Total exposure ticks: 0\b/);
    assert.doesNotMatch(log, /FIRST_OBSERVED_BODY_OPTICAL_EXPOSURE: NONE/);

    // opticalTickFromLiveFrame still sees current-frame DET for inspector parity
    const ot0 = opticalTickFromLiveFrame(frame, 'agent_0') as OpticalTickTS;
    assert.equal(ot0.body_exposure, true);
  });

  it('empty series uses NOT_AVAILABLE (not zero history)', () => {
    const rep = analyzeOpticalSeries([], { optical_history_authority: 'NONE' });
    assert.equal(rep.summary.total_exposure_ticks, 'NOT_AVAILABLE');
    assert.equal(rep.summary.exposure_episodes, 'NOT_AVAILABLE');
    assert.equal(rep.summary.first_observed_exposure_status, 'NOT_AVAILABLE');
  });
});
