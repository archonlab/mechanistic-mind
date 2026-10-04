import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  applyStatusFor,
  applyStatusLabel,
  buildCanonicalApplyPayload,
  canonicalSourceFromApplyResponse,
  draftPresetModified,
  mergeCanonicalIntoSnapshot,
  overlayMechanismEnabled,
  snapshotFromCanonical,
  snapshotFromEditors,
  snapshotFromRuntimeFrame,
  snapshotsEqual,
  uiFieldsFromSnapshot,
  type ExperimentSnapshot,
} from './experimentDraft.ts';

function baseSnap(over: Partial<ExperimentSnapshot> = {}): ExperimentSnapshot {
  return {
    seed: 17,
    width: 32,
    height: 32,
    ecology_preset: 'BASELINE_CLIMATE_DEFAULT',
    cognition_enabled: true,
    pe_cold_history_eviction: true,
    agent_count: 2,
    body_mass: 1,
    body_v_max: 0.4,
    public_preset: 'TIKTAALIK_BETA31',
    psc_motor_resolution: 'LOCO_FACTORIZED',
    mechanisms: { spatiotemporal_climate_ecology: true, physical_near_field_vision: true },
    vision: {
      enabled: true,
      radius: 3,
      visual_surface_discrimination: 'OFF',
      optical_mapping: 'INDEPENDENT',
      spatial_vision: 'LEGACY',
    },
    ...over,
  };
}

describe('experiment draft persistence across tabs', () => {
  it('keeps ecology, vision, and body edits in one snapshot', () => {
    let draft = baseSnap();
    draft = { ...draft, ecology_preset: 'GENTLE_FREE_MOVEMENT' };
    draft = {
      ...draft,
      vision: { ...draft.vision, radius: 1, spatial_vision: 'ANGULAR' },
    };
    draft = { ...draft, body_mass: 2.5, body_v_max: 0.2 };
    assert.equal(draft.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(draft.vision.radius, 1);
    assert.equal(draft.vision.spatial_vision, 'ANGULAR');
    assert.equal(draft.body_mass, 2.5);
    assert.equal(draft.body_v_max, 0.2);
    const active = baseSnap();
    assert.equal(snapshotsEqual(draft, active), false);
  });
});

describe('atomic apply payload', () => {
  it('emits one complete payload including every edited field', () => {
    const draft = baseSnap({
      ecology_preset: 'CURRENT_LEGACY',
      vision: {
        enabled: true,
        radius: 2,
        visual_surface_discrimination: 'RICH',
        optical_mapping: 'INDEPENDENT',
        spatial_vision: 'OCCLUSION',
      },
      body_mass: 3,
      mechanisms: {
        spatiotemporal_climate_ecology: false,
        physical_near_field_vision: true,
        contextual_predictive_organization: true,
      },
    });
    const payload = buildCanonicalApplyPayload(draft);
    assert.equal(payload.ecology_preset, 'CURRENT_LEGACY');
    assert.equal((payload.vision as any).radius, 2);
    assert.equal((payload.vision as any).spatial_vision, 'OCCLUSION');
    assert.equal((payload.agent_body as any).mass, 3);
    assert.equal((payload.mechanisms as any).spatiotemporal_climate_ecology, false);
    assert.equal((payload.mechanisms as any).contextual_predictive_organization, true);
    assert.equal(payload.public_preset, 'TIKTAALIK_BETA31');
    assert.equal(payload.psc_motor_resolution, 'LOCO_FACTORIZED');
  });

  it('keeps Acanthostega public_preset when Ecology/Predictive are overridden', () => {
    const baseline = snapshotFromEditors({
      seed: '17',
      width: '32',
      height: '32',
      ecologyPreset: 'BASELINE_CLIMATE_DEFAULT',
      cognitionEnabled: true,
      peColdHistoryEviction: true,
      twoAgentExperimental: true,
      bodyMass: '1',
      bodyVMax: '0.4',
      publicPreset: 'ACANTHOSTEGA_PHASE0',
      pscMotorResolution: 'LOCO_FACTORIZED',
      mechanisms: { spatiotemporal_climate_ecology: false },
      vision: {
        enabled: true,
        radius: 3,
        visual_surface_discrimination: 'OFF',
        optical_mapping: 'INDEPENDENT',
        spatial_vision: 'LEGACY',
      },
    });
    const draft = {
      ...baseline,
      ecology_preset: 'GENTLE_FREE_MOVEMENT',
      psc_motor_resolution: 'OBSERVED_COMPOSITE',
      pe_cold_history_eviction: false,
    };
    assert.equal(draft.public_preset, 'ACANTHOSTEGA_PHASE0');
    assert.equal(draftPresetModified(draft, baseline), true);
    const payload = buildCanonicalApplyPayload(draft);
    assert.equal(payload.public_preset, 'ACANTHOSTEGA_PHASE0');
    assert.equal(payload.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(payload.psc_motor_resolution, 'OBSERVED_COMPOSITE');
    assert.equal(payload.pe_cold_history_eviction, false);
  });

  it('omits public_preset only for explicit CUSTOM drafts', () => {
    const draft = snapshotFromEditors({
      seed: '17',
      width: '32',
      height: '32',
      ecologyPreset: 'BASELINE_CLIMATE_DEFAULT',
      cognitionEnabled: true,
      peColdHistoryEviction: true,
      twoAgentExperimental: true,
      bodyMass: '1',
      bodyVMax: '0.4',
      pscMotorResolution: 'LOCO_FACTORIZED',
      mechanisms: {},
      vision: {
        enabled: true,
        radius: 3,
        visual_surface_discrimination: 'OFF',
        optical_mapping: 'INDEPENDENT',
        spatial_vision: 'LEGACY',
      },
    });
    const payload = buildCanonicalApplyPayload(draft);
    assert.equal(payload.public_preset, undefined);
  });

  it('does not drop tab A when tab B is also set', () => {
    const draft = baseSnap({
      ecology_preset: 'GENTLE_FREE_MOVEMENT',
      body_mass: 2.2,
    });
    const payload = buildCanonicalApplyPayload(draft);
    assert.equal(payload.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal((payload.agent_body as any).mass, 2.2);
  });
});

describe('model preset into draft without applying', () => {
  it('merges Acanthostega canonical defaults while keeping later vision edits', () => {
    let draft = baseSnap();
    draft = mergeCanonicalIntoSnapshot(draft, {
      public_preset: 'ACANTHOSTEGA_PHASE0',
      ecology_preset: 'BASELINE_CLIMATE_DEFAULT',
      agent_count: 2,
      cognition_enabled: true,
      mechanisms: { persistent_prospective_control: true },
      vision: { enabled: true, radius: 3, spatial_vision: 'LEGACY' },
      psc_motor_resolution: 'LOCO_FACTORIZED',
    });
    draft = { ...draft, vision: { ...draft.vision, radius: 1 }, ecology_preset: 'GENTLE_FREE_MOVEMENT' };
    const payload = buildCanonicalApplyPayload(draft);
    assert.equal(payload.public_preset, 'ACANTHOSTEGA_PHASE0');
    assert.equal((payload.vision as any).radius, 1);
    assert.equal(payload.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal((payload.mechanisms as any).persistent_prospective_control, true);
  });
});

describe('apply failure keeps draft', () => {
  it('marks FAILED without reverting snapshot', () => {
    const draft = baseSnap({ seed: 99 });
    const active = baseSnap();
    const status = applyStatusFor(draft, active, false, true);
    assert.equal(status, 'FAILED');
    assert.equal(draft.seed, 99);
    assert.equal(active.seed, 17);
    assert.equal(applyStatusLabel(status), 'APPLY FAILED');
  });
});

describe('restore replaces draft from runtime snapshot', () => {
  it('overwrites previous-run editor values', () => {
    const previous = baseSnap({ seed: 1, ecology_preset: 'CURRENT_LEGACY' });
    const restored = baseSnap({ seed: 42, ecology_preset: 'BASELINE_CLIMATE_DEFAULT', public_preset: 'TIKTAALIK_BETA31' });
    assert.equal(snapshotsEqual(previous, restored), false);
    const synced = restored;
    assert.equal(synced.seed, 42);
    assert.equal(synced.ecology_preset, 'BASELINE_CLIMATE_DEFAULT');
    assert.equal(applyStatusFor(synced, restored, false, false), 'SAVED');
  });
});

describe('overlay draft mechanisms', () => {
  it('does not mutate catalog rows that were not edited', () => {
    const catalog = [{ id: 'a', enabled: true }, { id: 'b', enabled: false }];
    const over = overlayMechanismEnabled(catalog, { b: true });
    assert.equal(over[0].enabled, true);
    assert.equal(over[1].enabled, true);
  });
});

describe('snapshotFromRuntimeFrame restore sync', () => {
  it('builds active+draft from restored runtime fields', () => {
    const snap = snapshotFromRuntimeFrame(
      {
        header: { seed: 42, public_preset: 'TIKTAALIK_BETA31', target_tick: null },
        world: { width: 16, height: 20 },
        experiment: {
          ecology_preset: 'BASELINE_CLIMATE_DEFAULT',
          runtime: { cognition_enabled: true, agent_count: 2, pe_cold_history_eviction: true },
          agent_body: { mass: 2, v_max: 0.3 },
          observer: { ui_hz: 10, buffer_capacity: 512 },
        },
        physical: {
          near_field_exteroception: {
            vision_radius: 3,
            visual_surface_discrimination: 'OFF',
            optical_mapping: 'INDEPENDENT',
            spatial_vision: 'LEGACY',
          },
        },
      },
      [{ id: 'physical_near_field_vision', enabled: true }],
    );
    assert.equal(snap.seed, 42);
    assert.equal(snap.width, 16);
    assert.equal(snap.height, 20);
    assert.equal(snap.ecology_preset, 'BASELINE_CLIMATE_DEFAULT');
    assert.equal(snap.vision.radius, 3);
  });
});

describe('snapshotFromEditors', () => {
  it('round-trips UI fields used by Experiment tabs', () => {
    const snap = snapshotFromEditors({
      seed: '17',
      width: '16',
      height: '16',
      ecologyPreset: 'GENTLE_FREE_MOVEMENT',
      cognitionEnabled: true,
      peColdHistoryEviction: false,
      twoAgentExperimental: true,
      bodyMass: '2',
      bodyVMax: '0.3',
      publicPreset: 'ACANTHOSTEGA_PHASE0',
      pscMotorResolution: 'LOCO_FACTORIZED',
      mechanisms: { physical_near_field_vision: true },
      vision: {
        enabled: true,
        radius: 2,
        visual_surface_discrimination: 'LOW',
        optical_mapping: 'CORRELATED',
        spatial_vision: 'ANGULAR',
      },
    });
    assert.equal(snap.public_preset, 'ACANTHOSTEGA_PHASE0');
    assert.equal(snap.width, 16);
    assert.equal(snap.vision.radius, 2);
    assert.equal(snap.pe_cold_history_eviction, false);
    assert.equal(snap.psc_motor_resolution, 'LOCO_FACTORIZED');
    const payload = buildCanonicalApplyPayload(snap);
    assert.equal(payload.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(payload.psc_motor_resolution, 'LOCO_FACTORIZED');
    assert.equal(payload.pe_cold_history_eviction, false);
  });

  it('carries Predictive PSC motor resolution and mechanism flags', () => {
    const snap = snapshotFromEditors({
      seed: '17',
      width: '32',
      height: '32',
      ecologyPreset: 'BASELINE_CLIMATE_DEFAULT',
      cognitionEnabled: true,
      peColdHistoryEviction: false,
      twoAgentExperimental: false,
      bodyMass: '2',
      bodyVMax: '0.3',
      publicPreset: 'TIKTAALIK_BETA31',
      pscMotorResolution: 'OBSERVED_COMPOSITE',
      mechanisms: {
        prospective_scenario_competition: true,
        spatiotemporal_climate_ecology: false,
      },
      vision: {
        enabled: true,
        radius: 3,
        visual_surface_discrimination: 'OFF',
        optical_mapping: 'INDEPENDENT',
        spatial_vision: 'LEGACY',
      },
    });
    const payload = buildCanonicalApplyPayload(snap);
    assert.equal(payload.psc_motor_resolution, 'OBSERVED_COMPOSITE');
    assert.equal(payload.pe_cold_history_eviction, false);
    assert.equal((payload.mechanisms as any).prospective_scenario_competition, true);
    assert.equal((payload.mechanisms as any).spatiotemporal_climate_ecology, false);
  });

  it('preserves PSC auto-enable schedule separately from initial OFF', () => {
    const snap = snapshotFromEditors({
      seed: '17',
      width: '32',
      height: '32',
      ecologyPreset: 'GENTLE_FREE_MOVEMENT',
      cognitionEnabled: true,
      peColdHistoryEviction: true,
      twoAgentExperimental: true,
      bodyMass: '1',
      bodyVMax: '0.4',
      publicPreset: 'ACANTHOSTEGA_BETA4',
      pscMotorResolution: 'OBSERVED_COMPOSITE',
      pscOffTicks: 1000,
      mechanisms: {
        prospective_scenario_competition: false,
        experimental_physical_signal: false,
        oscillatory_signaling: true,
      },
      vision: {
        enabled: true,
        radius: 3,
        visual_surface_discrimination: 'RICH',
        optical_mapping: 'INDEPENDENT',
        spatial_vision: 'OCCLUSION',
      },
    });
    const payload = buildCanonicalApplyPayload(snap);
    assert.equal(payload.psc_off_ticks, 1000);
    assert.equal((payload.psc_schedule as any).psc_off_ticks, 1000);
    assert.equal((payload.mechanisms as any).prospective_scenario_competition, false);
    assert.equal(payload.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(payload.psc_motor_resolution, 'OBSERVED_COMPOSITE');
  });
});

describe('canonical apply round-trip hydrate', () => {
  it('keeps ecology and predictive fields from active_experiment, not visual-frame defaults', () => {
    const canonical = {
      seed: 17,
      ecology_preset: 'GENTLE_FREE_MOVEMENT',
      cognition_enabled: true,
      pe_cold_history_eviction: false,
      agent_count: 2,
      public_preset: 'TIKTAALIK_BETA31',
      psc_motor_resolution: 'OBSERVED_COMPOSITE',
      world: { width: 32, height: 32 },
      agent_body: { mass: 2.5, v_max: 0.2 },
      mechanisms: {
        spatiotemporal_climate_ecology: false,
        prospective_scenario_competition: true,
      },
      vision: { enabled: true, radius: 1, spatial_vision: 'ANGULAR' },
    };
    const frame = {
      active_experiment: canonical,
      header: { seed: 17, ecology_preset: 'BASELINE_CLIMATE_DEFAULT', psc_motor_resolution: undefined },
      experiment: { ecology_preset: 'BASELINE_CLIMATE_DEFAULT', runtime: {} },
    };
    const src = canonicalSourceFromApplyResponse(frame);
    const snap = snapshotFromCanonical(src);
    assert.ok(snap);
    assert.equal(snap.ecology_preset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(snap.psc_motor_resolution, 'OBSERVED_COMPOSITE');
    assert.equal(snap.pe_cold_history_eviction, false);
    assert.equal(snap.mechanisms.spatiotemporal_climate_ecology, false);
    assert.equal(snap.mechanisms.prospective_scenario_competition, true);
    assert.equal(snap.vision.radius, 1);
    const visual = snapshotFromRuntimeFrame(frame, [], {});
    assert.equal(visual.psc_motor_resolution, 'LOCO_FACTORIZED');
    assert.notEqual(visual.ecology_preset, snap.ecology_preset);
  });

  it('cross-tab canonical hydrate keeps Ecology, Predictive, Vision, Body, Model', () => {
    const src = {
      public_preset: 'ACANTHOSTEGA_PHASE0',
      ecology_preset: 'GENTLE_FREE_MOVEMENT',
      psc_motor_resolution: 'OBSERVED_COMPOSITE',
      pe_cold_history_eviction: false,
      cognition_enabled: true,
      agent_count: 2,
      seed: 17,
      world: { width: 16, height: 20 },
      agent_body: { mass: 2.5, v_max: 0.2 },
      vision: { enabled: true, radius: 1, spatial_vision: 'ANGULAR' },
      mechanisms: {
        spatiotemporal_climate_ecology: false,
        prospective_scenario_competition: true,
        physical_near_field_vision: true,
      },
    };
    const snap = snapshotFromCanonical(src)!;
    const fields = uiFieldsFromSnapshot(snap);
    assert.equal(fields.ecologyPreset, 'GENTLE_FREE_MOVEMENT');
    assert.equal(fields.peColdHistoryEviction, false);
    assert.equal(fields.bodyMass, '2.5');
    assert.equal(fields.twoAgentExperimental, true);
    assert.equal(snap.psc_motor_resolution, 'OBSERVED_COMPOSITE');
    assert.equal(snap.vision.radius, 1);
    assert.equal(snap.public_preset, 'ACANTHOSTEGA_PHASE0');
    const payload = buildCanonicalApplyPayload(snap);
    assert.equal(payload.ecology_preset, src.ecology_preset);
    assert.equal(payload.psc_motor_resolution, src.psc_motor_resolution);
    assert.equal(payload.public_preset, src.public_preset);
    assert.equal((payload.vision as any).radius, 1);
    assert.equal((payload.agent_body as any).mass, 2.5);
  });
});
