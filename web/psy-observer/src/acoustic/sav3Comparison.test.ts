import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  A5_BAR_MAX,
  SAV3_A3_BADGE,
  SAV3_SCHEMA,
  SAV3_TITLE,
  SAV3_WARNING,
  a3BarWidthPx,
  a5BarWidthPx,
  asymmetryA5,
  bandRowFromTrace,
  transformPass,
} from './sav3Comparison.ts';

const root = dirname(fileURLToPath(import.meta.url));

describe('SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1', () => {
  it('identity and warnings match contract', () => {
    assert.equal(SAV3_SCHEMA, 'SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1');
    assert.equal(SAV3_TITLE, 'PHYSICAL FIELD → ORGANISM RECEPTORS');
    assert.match(SAV3_WARNING, /ONLY A5 IS ORGANISM-ACCESSIBLE/);
    assert.match(SAV3_A3_BADGE, /RESEARCHER-ONLY/);
  });

  it('A5 bars use fixed [0,1] scale without per-trace gain', () => {
    assert.equal(A5_BAR_MAX, 1);
    assert.equal(a5BarWidthPx(0, 48), 0);
    assert.equal(a5BarWidthPx(0.5, 48), 24);
    assert.equal(a5BarWidthPx(1, 48), 48);
    assert.equal(a5BarWidthPx(2, 48), 48); // clipped to 1 for display width only
  });

  it('A3 bars mark overflow beyond clip unit; no per-row normalization', () => {
    const ok = a3BarWidthPx(0.5, 1, 48);
    assert.equal(ok.width, 24);
    assert.equal(ok.overflow, false);
    const ov = a3BarWidthPx(2.0, 1, 48);
    assert.equal(ov.width, 48);
    assert.equal(ov.overflow, true);
  });

  it('transform PASS/MISMATCH from recorded residual only', () => {
    assert.equal(transformPass({ within_tolerance: true, max_abs_residual: 0, tolerance: 1e-12 }).pass, true);
    assert.equal(transformPass({ within_tolerance: false, max_abs_residual: 0.1, tolerance: 1e-12 }).pass, false);
  });

  it('band rows read recorded fields without inventing A5', () => {
    const tr = {
      a3: {
        left_receptor_band_energy: [0, 1, 2, 0, 0, 0],
        right_receptor_band_energy: [0, 0, 0.5, 0, 0, 0],
      },
      a4: {
        sensor_scale: 2,
        per_band_lower_clipped_left: [false, false, false, false, false, false],
        per_band_upper_clipped_left: [false, false, true, false, false, false],
        per_band_lower_clipped_right: [false, false, false, false, false, false],
        per_band_upper_clipped_right: [false, false, false, false, false, false],
        transform_residual: {
          per_band_abs_residual_left: [0, 0, 0, 0, 0, 0],
          per_band_abs_residual_right: [0, 0, 0, 0, 0, 0],
        },
        per_band_loss_accounting: [],
      },
      a5: {
        left_receptor_channels: [0, 0.5, 1, 0, 0, 0],
        right_receptor_channels: [0, 0, 0.25, 0, 0, 0],
      },
    };
    const row = bandRowFromTrace(tr, 2);
    assert.equal(row.a3L, 2);
    assert.equal(row.a5L, 1);
    assert.equal(row.clipL, 'UPPER');
    assert.deepEqual(asymmetryA5(tr.a5.left_receptor_channels, tr.a5.right_receptor_channels)[2], 0.75);
  });

  it('HEARING mounts SAV3 without remounting C1/SAV2 engines', () => {
    const hw = readFileSync(join(root, 'HearingWorkspacePanel.tsx'), 'utf8');
    assert.ok(hw.includes('SelectedOrganismPhysicalFieldComparisonPanel'));
    assert.ok(hw.includes('SelectedOrganismAuditoryViewPanel'));
    assert.ok(hw.includes('CanonicalSonificationPanel'));
    const mountsC1 = hw.split('<CanonicalSonificationPanel').length - 1;
    const mountsSav2 = hw.split('<SelectedOrganismAuditoryViewPanel').length - 1;
    const mountsSav3 = hw.split('<SelectedOrganismPhysicalFieldComparisonPanel').length - 1;
    assert.equal(mountsC1, 1);
    assert.equal(mountsSav2, 1);
    assert.equal(mountsSav3, 1);
    const panel = readFileSync(join(root, 'SelectedOrganismPhysicalFieldComparisonPanel.tsx'), 'utf8');
    assert.ok(panel.includes('SAV3_WARNING'));
    assert.ok(panel.includes('sav3-matrix'));
    assert.equal(panel.includes('AudioContext'), false);
    assert.equal(panel.includes('PlaybackEngine'), false);
  });
});
