/**
 * Vision forensics — Analyzer-side only (node:test).
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzeOpticalSeries,
  buildVisionEvents,
  channelOverlap,
  type OpticalTickTS,
} from './visionForensics.ts';

function tick(partial: Partial<OpticalTickTS> & { tick: number }): OpticalTickTS {
  return {
    observer_body_id: 'body-0',
    observer_agent_id: 'agent_0',
    exo: { exo_0: 0, exo_1: 0.2, exo_2: 0 },
    neighbors: [
      {
        cell: [17, 16],
        inside_fov: true,
        surface_response: 0,
        body_optical: 0.65,
        composed_optical: 0.65,
        final_contribution: 0.18,
        source_body_ids: ['body-1'],
      },
    ],
    selected_source_body_id: 'body-1',
    coverage: 'CONTIGUOUS',
    ...partial,
  };
}

describe('visionForensics', () => {
  it('detects BODY_VISUAL_ENTRY and defaults cognition link NOT_ESTABLISHED', () => {
    const rep = analyzeOpticalSeries([tick({ tick: 1 })]);
    assert.equal(rep.summary.foreign_body_visual_entries, 1);
    assert.equal(rep.summary.cognition_linkage_default, 'NOT_ESTABLISHED');
    const edges = rep.causal_chains[0].edges;
    assert.equal(edges[edges.length - 1]?.link, 'NOT_ESTABLISHED');
  });

  it('does not count body behind FOV as visual entry', () => {
    const behind = tick({
      tick: 1,
      neighbors: [
        {
          cell: [15, 16],
          inside_fov: false,
          surface_response: 0,
          body_optical: 0.65,
          composed_optical: 0.65,
          final_contribution: 0,
          source_body_ids: ['body-1'],
        },
      ],
    });
    assert.equal(analyzeOpticalSeries([behind]).summary.foreign_body_visual_entries, 0);
  });

  it('classifies VISION_WITHOUT_CONTACT vs FIELD/contact', () => {
    assert.equal(channelOverlap(tick({ tick: 1 })), 'VISION_WITHOUT_CONTACT');
    assert.equal(channelOverlap(tick({ tick: 1, field_reception: true })), 'VISION_WITH_SIGNAL');
    assert.equal(channelOverlap(tick({ tick: 1, contact: true })), 'VISION_PLUS_CONTACT');
  });

  it('env-only optical (body_opt=0) is not BODY_OPTICAL_EXPOSURE', () => {
    const envOnly = tick({
      tick: 1,
      neighbors: [
        {
          cell: [17, 16],
          inside_fov: true,
          surface_response: 0.5,
          body_optical: 0,
          composed_optical: 0.5,
          final_contribution: 0.2,
          source_body_ids: [],
        },
      ],
      selected_source_body_id: null,
      exo_without_body: { exo_0: 0, exo_1: 0.2, exo_2: 0 },
      foreign_body_total: 0,
      body_exposure: false,
    });
    assert.equal(analyzeOpticalSeries([envOnly]).summary.foreign_body_visual_entries, 0);
  });

  it('uses foreign_body_total authority for exposure', () => {
    const t = tick({
      tick: 2,
      body_exposure: true,
      foreign_body_total: 0.12,
      foreign_body_contribution: { exo_0: 0, exo_1: 0.12, exo_2: 0 },
      exo_without_body: { exo_0: 0, exo_1: 0.08, exo_2: 0 },
    });
    const rep = analyzeOpticalSeries([t]);
    assert.equal(rep.summary.exposure_episodes, 1);
    assert.ok(Number(rep.summary.by_agent!.agent_0.peak_body_optical_contribution) >= 0.12);
  });

  it('sparse GAP breaks continuity without inventing continuous exposure', () => {
    const events = buildVisionEvents([
      tick({ tick: 1 }),
      tick({ tick: 2, coverage: 'GAP' }),
      tick({ tick: 5 }),
    ]);
    const entries = events.filter((e) => e.type === 'BODY_OPTICAL_ENTER');
    assert.equal(entries.length, 2);
  });
});
