/** Researcher-only VOLUME incremental merge helpers (P2). */

export function resolveVolumeDescription(desc: any, heldStatic: any | null): {
  description: any;
  volumes: any[];
  bodies: any[];
  objects: any[];
  staticPayloadId: string | null;
  kind: string;
  rejected: string | null;
} {
  const root = desc || {};
  const inc = root.observer_volume_incremental || null;
  const kind = String(inc?.kind || root.incremental_wire_kind || 'FULL');
  const staticId = String(
    inc?.volume_static?.static_payload_id
    || inc?.volume_dynamic?.static_payload_id
    || root.static_payload_id
    || '',
  ) || null;

  if (kind === 'DYNAMIC') {
    const heldId = heldStatic?.static_payload_id ? String(heldStatic.static_payload_id) : null;
    const dynId = inc?.volume_dynamic?.static_payload_id
      ? String(inc.volume_dynamic.static_payload_id)
      : staticId;
    if (!heldStatic || !heldId) {
      return {
        description: root,
        volumes: root.occupancy_volumes || [],
        bodies: root.bodies || [],
        objects: root.resource_objects || [],
        staticPayloadId: staticId,
        kind,
        rejected: 'MISSING_BASE',
      };
    }
    if (dynId && heldId !== dynId) {
      return {
        description: root,
        volumes: heldStatic.occupancy_volumes || [],
        bodies: root.bodies || [],
        objects: root.resource_objects || [],
        staticPayloadId: staticId,
        kind,
        rejected: 'STALE_DELTA',
      };
    }
    const volumes = heldStatic.occupancy_volumes || [];
    const bodies = list(inc?.volume_dynamic?.bodies ?? root.bodies);
    const objects = list(inc?.volume_dynamic?.resource_objects ?? root.resource_objects);
    const tombs = list(inc?.volume_dynamic?.entity_tombstones);
    const dead = new Set(tombs.map((t: any) => String(t.entity_id || '')));
    return {
      description: {
        ...root,
        ...heldStatic,
        occupancy_volumes: volumes,
        occupancy_volume_count: volumes.length,
        bodies: bodies.filter((b: any) => !dead.has(String(b.body_id || ''))),
        resource_objects: objects.filter((o: any) => !dead.has(String(o.object_id || ''))),
        available: true,
      },
      volumes,
      bodies: bodies.filter((b: any) => !dead.has(String(b.body_id || ''))),
      objects: objects.filter((o: any) => !dead.has(String(o.object_id || ''))),
      staticPayloadId: heldId,
      kind,
      rejected: null,
    };
  }

  const st = inc?.volume_static || null;
  return {
    description: root,
    volumes: root.occupancy_volumes_static_omitted
      ? (heldStatic?.occupancy_volumes || root.occupancy_volumes || [])
      : (root.occupancy_volumes || []),
    bodies: root.bodies || [],
    objects: root.resource_objects || [],
    staticPayloadId: staticId || (st?.static_payload_id ? String(st.static_payload_id) : null),
    kind,
    rejected: null,
  };
}

function list(x: any): any[] {
  return Array.isArray(x) ? x : [];
}
