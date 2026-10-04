/**
 * P2 VOLUME incremental merge helpers — source-level contract tests.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveVolumeDescription } from './volumeIncremental.ts';

const root = dirname(fileURLToPath(import.meta.url));

describe('volumeIncremental P2', () => {
  it('merges DYNAMIC onto held static and applies tombstones', () => {
    const held = {
      static_payload_id: 'abc',
      occupancy_volumes: [{ interval_id: 'I|0|0|0|1|soil' }],
    };
    const desc = {
      incremental_wire_kind: 'DYNAMIC',
      observer_volume_incremental: {
        kind: 'DYNAMIC',
        volume_dynamic: {
          static_payload_id: 'abc',
          bodies: [{ body_id: 'b1', sim_x: 1 }],
          resource_objects: [{ object_id: 'o1' }, { object_id: 'o2' }],
          entity_tombstones: [{ entity_id: 'o2', kind: 'RESOURCE_OBJECT' }],
        },
      },
      bodies: [],
      resource_objects: [],
    };
    const r = resolveVolumeDescription(desc, held);
    assert.equal(r.rejected, null);
    assert.equal(r.volumes.length, 1);
    assert.equal(r.bodies[0].sim_x, 1);
    assert.equal(r.objects.length, 1);
    assert.equal(r.objects[0].object_id, 'o1');
  });

  it('rejects missing base and stale delta', () => {
    const desc = {
      observer_volume_incremental: {
        kind: 'DYNAMIC',
        volume_dynamic: { static_payload_id: 'new' },
      },
    };
    assert.equal(resolveVolumeDescription(desc, null).rejected, 'MISSING_BASE');
    assert.equal(
      resolveVolumeDescription(desc, { static_payload_id: 'old', occupancy_volumes: [] }).rejected,
      'STALE_DELTA',
    );
  });

  it('OccupancyVolumeView holds static, acks payload id, suspends, single camera reset on staticId', () => {
    const view = readFileSync(resolve(root, '../components/OccupancyVolumeView.tsx'), 'utf8');
    assert.ok(view.includes('volume_static_payload_id'));
    assert.ok(view.includes('heldStaticRef'));
    assert.ok(view.includes('facesCacheRef'));
    assert.ok(view.includes('facesFlat') || view.includes('projectedCacheRef'));
    assert.ok(view.includes('if (suspended) return'));
    assert.ok(view.includes('[tile.width, tile.height, staticId, suspended]'));
    assert.ok(view.includes('resolveVolumeDescription'));
  });

  it('WorldPane mounts one OccupancyVolumeView with suspended prop', () => {
    const pane = readFileSync(resolve(root, '../chrome/WorldPane.tsx'), 'utf8');
    assert.equal((pane.match(/<OccupancyVolumeView/g) || []).length, 1);
    assert.ok(pane.includes('suspended={renderSuspended}'));
  });
});
