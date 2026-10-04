/** Dual FPV × Hearing lifecycle — fails on pre-repair Vision-subtab gate / cache clear. */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  absorbLatestExactByAgent,
  liveState,
  traceForAgent,
  wantEyeDockDualFpvSubscription,
  type ExactTraceLike,
} from './eyeDockDualFpvLifecycle.ts';

const root = dirname(fileURLToPath(import.meta.url));
const src = (...p: string[]) => readFileSync(join(root, ...p), 'utf8');

function tr(agentId: string, tick: number, gen = 1, extras: Partial<ExactTraceLike> = {}): ExactTraceLike {
  return {
    agent_id: agentId,
    trace_id: `${agentId}-t${tick}-g${gen}`,
    observation_tick: tick,
    receptor_tick: tick,
    runtime_generation: gen,
    true_zero_exact_trace: false,
    ...extras,
  };
}

describe('Dual FPV Hearing lifecycle ownership', () => {
  it('1–2: both agents LIVE before Hearing; dock-open keeps dual subscription on Hearing', () => {
    assert.equal(wantEyeDockDualFpvSubscription({ open: true, centralOwnsSensory: null }), true);
    assert.equal(wantEyeDockDualFpvSubscription({ open: true, centralOwnsSensory: 'HEARING' }), true);
    assert.equal(wantEyeDockDualFpvSubscription({ open: true, centralOwnsSensory: 'VISION' }), true);
    assert.equal(wantEyeDockDualFpvSubscription({ open: false, centralOwnsSensory: 'VISION' }), true);
    assert.equal(wantEyeDockDualFpvSubscription({ open: false, centralOwnsSensory: 'HEARING' }), true);
    // Pre-bug required sensory===VISION for dual FPV interest AND disabled dual when FPV owned center.
    const dock = src('TiktaalikEyeDock.tsx');
    assert.match(dock, /wantEyeDockDualFpvSubscription/);
    assert.doesNotMatch(dock, /want = open && centralOwnsSensory !== 'VISION'/);
    assert.doesNotMatch(dock, /want\s*=\s*[\s\S]{0,80}sensory === 'VISION'/);
  });

  it('3–6: Listen World / Agent / stop preserve retained dual map (no clear on omission)', () => {
    const retained: Record<string, ExactTraceLike> = {};
    absorbLatestExactByAgent(retained, {
      agent_0: tr('agent_0', 10),
      agent_1: tr('agent_1', 11),
    });
    // Simulate frames without dual map (old Vision-gated disable) during World/Agent playback.
    absorbLatestExactByAgent(retained, undefined);
    absorbLatestExactByAgent(retained, null);
    absorbLatestExactByAgent(retained, {});
    const viewMissing = { latest: tr('agent_0', 12), selected_agent_id: 'agent_0' };
    assert.equal(liveState(traceForAgent(viewMissing, 'agent_0', retained)), 'LIVE');
    assert.equal(liveState(traceForAgent(viewMissing, 'agent_1', retained)), 'LIVE');
    assert.equal(traceForAgent(viewMissing, 'agent_0', retained)?.trace_id, 'agent_0-t10-g1');
    assert.equal(traceForAgent(viewMissing, 'agent_1', retained)?.trace_id, 'agent_1-t11-g1');
  });

  it('5,10: local Hearing selector must not mutate global selected organism (source)', () => {
    const hw = src('../acoustic/HearingWorkspacePanel.tsx');
    assert.match(hw, /Do NOT mutate global selected simulation agent/);
    assert.match(hw, /does not change the globally selected simulation agent/);
    assert.doesNotMatch(hw, /selectObserverAgent|postControl\(['"]select/);
  });

  it('7–8: Hearing→Vision and repeated tab switches do not reduce cache to one agent', () => {
    const retained: Record<string, ExactTraceLike> = {};
    absorbLatestExactByAgent(retained, { agent_0: tr('agent_0', 1), agent_1: tr('agent_1', 1) });
    for (let i = 0; i < 8; i++) {
      // alternate: dual map present / omitted (tab thrash)
      if (i % 2 === 0) {
        absorbLatestExactByAgent(retained, {
          agent_0: tr('agent_0', 20 + i),
          agent_1: tr('agent_1', 20 + i),
        });
      } else {
        absorbLatestExactByAgent(retained, undefined);
      }
    }
    assert.equal(Object.keys(retained).sort().join(','), 'agent_0,agent_1');
    assert.notEqual(retained.agent_0.trace_id, retained.agent_1.trace_id);
  });

  it('9: FPV card selection changes availability semantics only via global select callback (source)', () => {
    const dual = src('EyeDockVisionWorkspace.tsx');
    const life = src('eyeDockDualFpvLifecycle.ts');
    assert.match(dual, /onSelectAgent\?\.\(idx\)/);
    assert.match(life, /Never cross-copy agents|selected-latest match only/);
    assert.match(life, /String\(tr\.agent_id \|\| agentId\) !== String\(agentId\)/);
  });

  it('11–12: agent trace IDs and generations never cross', () => {
    const retained: Record<string, ExactTraceLike> = {};
    absorbLatestExactByAgent(retained, {
      agent_0: tr('agent_0', 5, 7),
      // hostile: wrong agent_id under agent_1 key must be rejected
      agent_1: { ...tr('agent_0', 6, 8), agent_id: 'agent_0' } as ExactTraceLike,
    });
    assert.ok(retained.agent_0);
    assert.equal(retained.agent_1, undefined);
    absorbLatestExactByAgent(retained, { agent_1: tr('agent_1', 6, 8) });
    const view = {
      latest_exact_by_agent: {
        agent_0: tr('agent_0', 50, 7),
        agent_1: tr('agent_1', 51, 8),
      },
    };
    const a0 = traceForAgent(view, 'agent_0', retained)!;
    const a1 = traceForAgent(view, 'agent_1', retained)!;
    assert.notEqual(a0.trace_id, a1.trace_id);
    assert.equal(a0.runtime_generation, 7);
    assert.equal(a1.runtime_generation, 8);
    assert.equal(a0.observation_tick, 50);
    assert.equal(a1.observation_tick, 51);
  });

  it('13: missing remains UNAVAILABLE; true zero remains ZERO', () => {
    assert.equal(liveState(null), 'UNAVAILABLE');
    assert.equal(liveState(undefined), 'UNAVAILABLE');
    assert.equal(liveState(tr('agent_0', 1, 1, { true_zero_exact_trace: true })), 'ZERO');
    assert.equal(liveState(tr('agent_0', 1)), 'LIVE');
    const retained = {};
    const view = { latest: null, selected_agent_id: 'agent_0' };
    assert.equal(traceForAgent(view, 'agent_1', retained), null);
    assert.equal(liveState(traceForAgent(view, 'agent_1', retained)), 'UNAVAILABLE');
  });

  it('14–16: dock close disables subscription; retain traces; no per-card / Vision-tab gate', () => {
    assert.equal(wantEyeDockDualFpvSubscription({ open: false }), false);
    assert.equal(wantEyeDockDualFpvSubscription({ open: false, centralOwnsSensory: null }), false);
    assert.equal(wantEyeDockDualFpvSubscription({ open: true, centralOwnsSensory: 'VISION' }), true);
    const interest = src('../observer/interest.ts');
    assert.match(interest, /eye_dock_dual_fpv/);
    assert.match(interest, /Eye dock open \(Vision or Hearing\)/);
    const dock = src('TiktaalikEyeDock.tsx');
    assert.match(dock, /dockHidden=\{visionSuspended\}/);
    assert.match(dock, /Dual exact FPV delivery is dock-owned/);
    const dual = src('EyeDockVisionWorkspace.tsx');
    assert.match(dual, /absorbLatestExactByAgent/);
    assert.match(dual, /retainedExactByAgent/);
    assert.doesNotMatch(dual, /setInterval|new WebSocket|fetch\(/);
  });

  it('18: display-only / Hearing sources do not Apply-and-reset', () => {
    const dock = src('TiktaalikEyeDock.tsx');
    const hw = src('../acoustic/HearingWorkspacePanel.tsx');
    const dual = src('EyeDockVisionWorkspace.tsx');
    for (const s of [dock, hw, dual]) {
      assert.doesNotMatch(s, /APPLY_AND_RESET|postControl\(['"]apply/);
    }
  });
});
