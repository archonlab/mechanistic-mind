/**
 * ACTIVE_SENSOR_ORIENTATION is an articulated-head availability flag,
 * not "vision FOV heading present". FOV uses sensor_forward_axis / body θ
 * even when ASO === NOT_AVAILABLE.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

function reportActiveSensorOrientation(physical: any) {
  const aso = String(
    physical?.orientation?.ACTIVE_SENSOR_ORIENTATION
    || physical?.near_field_exteroception?.ACTIVE_SENSOR_ORIENTATION
    || 'NOT_AVAILABLE',
  );
  const fovAxis =
    physical?.near_field_exteroception?.sensor_forward_axis
    ?? physical?.near_field_exteroception?.head_world_heading
    ?? physical?.orientation?.theta
    ?? null;
  return { aso, fovAxis };
}

describe('ACTIVE_SENSOR_ORIENTATION UI mapping', () => {
  it('reports AVAILABLE from orientation when articulated head ON', () => {
    const r = reportActiveSensorOrientation({
      orientation: {
        ACTIVE_SENSOR_ORIENTATION: 'AVAILABLE',
        articulated_head_enabled: true,
        head_world_heading: 1.2,
        theta: 0.5,
      },
      near_field_exteroception: {
        ACTIVE_SENSOR_ORIENTATION: 'AVAILABLE',
        sensor_forward_axis: 1.2,
      },
    });
    assert.equal(r.aso, 'AVAILABLE');
    assert.equal(r.fovAxis, 1.2);
  });

  it('keeps NOT_AVAILABLE when head OFF even if FOV axis exists (vision ON)', () => {
    const r = reportActiveSensorOrientation({
      orientation: {
        ACTIVE_SENSOR_ORIENTATION: 'NOT_AVAILABLE',
        articulated_head_enabled: false,
        theta: 0.75,
      },
      near_field_exteroception: {
        ACTIVE_SENSOR_ORIENTATION: 'NOT_AVAILABLE',
        sensor_forward_axis: 0.75,
        body_theta: 0.75,
        perception_enabled: true,
      },
    });
    assert.equal(r.aso, 'NOT_AVAILABLE');
    assert.equal(r.fovAxis, 0.75);
  });

  it('does not invent AVAILABLE when fields absent', () => {
    const r = reportActiveSensorOrientation({});
    assert.equal(r.aso, 'NOT_AVAILABLE');
    assert.equal(r.fovAxis, null);
  });
});
