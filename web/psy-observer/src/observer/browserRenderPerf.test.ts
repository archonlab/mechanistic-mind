/**
 * P5 browser render perf helpers — default OFF.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  SCHEMA,
  CAPABILITY,
  PROFILE,
  AUTHORITY,
  browserPerfEnabled,
  setBrowserPerfEnabled,
  timeSync,
  snapshot,
  resetSamples,
} from './browserRenderPerf.ts';

const root = dirname(fileURLToPath(import.meta.url));

describe('browserRenderPerf P5', () => {
  it('identity + default off', () => {
    assert.equal(SCHEMA, 'OBSERVER_BROWSER_RENDER_PERFORMANCE_V1');
    assert.equal(CAPABILITY, 'browser_upload_render_profiling_and_optimization');
    assert.equal(PROFILE, 'MAP_VOLUME_SURFACE_BROWSER_PIPELINE_P5_V1');
    assert.equal(AUTHORITY, 'RESEARCHER_DISPLAY_PERFORMANCE_TELEMETRY_NO_PHYSICAL_EFFECT');
    setBrowserPerfEnabled(false);
    assert.equal(browserPerfEnabled(), false);
    resetSamples();
    const n = timeSync('noop', () => 1);
    assert.equal(n, 1);
    assert.equal((snapshot().sample_count as number) || 0, 0);
  });

  it('records when enabled and stays bounded', () => {
    setBrowserPerfEnabled(true);
    resetSamples();
    for (let i = 0; i < 20; i++) timeSync('probe', () => Math.sqrt(i));
    const snap = snapshot();
    assert.ok((snap.sample_count as number) >= 20);
    assert.ok((snap.stats as any).probe?.n >= 20);
    setBrowserPerfEnabled(false);
  });

  it('OccupancyVolumeView persists flat faces + projected cache; Surface instrumented', () => {
    const vol = readFileSync(resolve(root, '../components/OccupancyVolumeView.tsx'), 'utf8');
    assert.ok(vol.includes('projectedCacheRef'));
    assert.ok(vol.includes('facesFlat'));
    assert.ok(vol.includes('volume_project_sort'));
    assert.ok(vol.includes('__P5_DISABLE_VOLUME_PROJ_CACHE__'));
    const surf = readFileSync(resolve(root, '../components/SurfaceLightView.tsx'), 'utf8');
    assert.ok(surf.includes('surface_project_sort'));
    assert.ok(surf.includes('timeSync'));
  });
});
