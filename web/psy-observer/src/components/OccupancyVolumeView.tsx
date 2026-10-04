/** RESEARCHER PHYSICAL WORLD VOLUME VIEW — NOT ORGANISM VISION.
 * Consumes VW1 occupancy render description. Camera never mutates simulation.
 * P2: persistent static occupancy buffers; dynamic body/RO updates only.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  defaultOrbitCamera,
  projectPoint,
  prismFaces,
  materialDisplayColor,
  simToRender,
  cameraEye,
  type OrbitCamera,
} from '../observer/occupancyVolumeProjection';
import { resolveVolumeDescription } from '../observer/volumeIncremental';
import { timeSync } from '../observer/browserRenderPerf';

type Props = {
  renderDescription: any;
  onSelectVolume?: (info: any) => void;
  /** P1: when true, skip geometry rebuild / canvas draw (tab hidden or pending). */
  suspended?: boolean;
};

type HeldStatic = {
  static_payload_id: string;
  occupancy_volumes: any[];
  world_tile?: any;
  occupancy_digest?: string;
};

async function ackHeldStatic(id: string | null) {
  try {
    await fetch('/api/observer/detail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume_static_payload_id: id }),
    });
  } catch {
    /* best-effort */
  }
}

export function OccupancyVolumeView({ renderDescription, onSelectVolume, suspended = false }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const camRef = useRef<OrbitCamera>(defaultOrbitCamera(32, 32));
  const drag = useRef<{ x: number; y: number; mode: 'orbit' | 'pan' } | null>(null);
  const heldStaticRef = useRef<HeldStatic | null>(null);
  const facesCacheRef = useRef<{ staticId: string; facesFlat: ReturnType<typeof prismFaces> } | null>(null);
  const projectedCacheRef = useRef<{
    key: string;
    polys: Array<{ pts: Array<{ u: number; v: number; depth: number }>; material: string }>;
  } | null>(null);
  const staticLayerRef = useRef<{ key: string; canvas: HTMLCanvasElement } | null>(null);
  const [camTick, setCamTick] = useState(0);
  const [rejectNotice, setRejectNotice] = useState<string | null>(null);

  const resolved = useMemo(
    () => resolveVolumeDescription(renderDescription, heldStaticRef.current),
    [renderDescription],
  );

  useEffect(() => {
    const inc = renderDescription?.observer_volume_incremental || null;
    const kind = String(inc?.kind || renderDescription?.incremental_wire_kind || resolved.kind || 'FULL');
    if (kind === 'FULL' || kind === 'RESET') {
      const st = inc?.volume_static;
      const vols = st?.occupancy_volumes
        || (renderDescription?.occupancy_volumes_static_omitted ? null : renderDescription?.occupancy_volumes);
      const sid = String(st?.static_payload_id || renderDescription?.static_payload_id || resolved.staticPayloadId || '');
      if (sid && Array.isArray(vols) && vols.length) {
        heldStaticRef.current = {
          static_payload_id: sid,
          occupancy_volumes: vols,
          world_tile: st?.world_tile || renderDescription?.world_tile,
          occupancy_digest: st?.occupancy_digest || renderDescription?.occupancy_digest,
        };
        facesCacheRef.current = null;
        projectedCacheRef.current = null;
        staticLayerRef.current = null;
        void ackHeldStatic(sid);
        setRejectNotice(null);
      }
    }
    if (resolved.rejected) {
      setRejectNotice(resolved.rejected);
      if (resolved.rejected === 'MISSING_BASE' || resolved.rejected === 'STALE_DELTA') {
        heldStaticRef.current = null;
        facesCacheRef.current = null;
        projectedCacheRef.current = null;
        staticLayerRef.current = null;
        void ackHeldStatic(null);
      }
    }
  }, [renderDescription, resolved.kind, resolved.rejected, resolved.staticPayloadId]);

  const available = Boolean(resolved.description?.available ?? renderDescription?.available);
  const tile = resolved.description?.world_tile
    || heldStaticRef.current?.world_tile
    || { width: 32, height: 32 };
  const staticId = resolved.staticPayloadId || heldStaticRef.current?.static_payload_id || '';
  const volumes = resolved.volumes;
  const bodies = resolved.bodies;
  const objects = resolved.objects;
  const dynRev = String(renderDescription?.dynamic_revision || '');

  const faces = useMemo(() => {
    if (facesCacheRef.current && facesCacheRef.current.staticId === staticId) {
      return facesCacheRef.current.facesFlat;
    }
    const expanded = timeSync('volume_geometry_expand', () => {
      const nested = volumes.map((v) => prismFaces(v));
      return nested.flat();
    }, { prism_count: volumes.length });
    if (staticId && expanded.length) {
      facesCacheRef.current = { staticId, facesFlat: expanded };
      projectedCacheRef.current = null;
    }
    return expanded;
  }, [volumes, staticId]);

  // Camera resets only on static base / tile change — not on body motion.
  useEffect(() => {
    if (suspended) return;
    camRef.current = defaultOrbitCamera(Number(tile.width) || 32, Number(tile.height) || 32);
    setCamTick((t) => t + 1);
  }, [tile.width, tile.height, staticId, suspended]);

  useEffect(() => {
    if (suspended) return;
    const canvas = ref.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    const W = Math.max(320, parent?.clientWidth || 640);
    const H = Math.max(240, parent?.clientHeight || 420);
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#12151a';
    ctx.fillRect(0, 0, W, H);

    if (!available) {
      ctx.fillStyle = '#9aa3ad';
      ctx.font = '13px sans-serif';
      ctx.fillText('VOLUME VIEW UNAVAILABLE · VW1 occupancy inactive / legacy session', 16, 28);
      ctx.fillText('Does not fabricate volumetric world from heightfield.', 16, 48);
      return;
    }

    const cam = camRef.current;
    const w = Number(tile.width) || 32;
    const h = Number(tile.height) || 32;
    const ground = [
      simToRender(0, 0, 0),
      simToRender(w, 0, 0),
      simToRender(w, h, 0),
      simToRender(0, h, 0),
    ].map((p) => projectPoint(p, cam, W, H));
    ctx.strokeStyle = '#2a3340';
    ctx.beginPath();
    ground.forEach((p, i) => (i ? ctx.lineTo(p.u, p.v) : ctx.moveTo(p.u, p.v)));
    ctx.closePath();
    ctx.stroke();

    const camKey = [
      staticId,
      W,
      H,
      Number(cam.yaw).toFixed(5),
      Number(cam.pitch).toFixed(5),
      Number(cam.distance).toFixed(4),
      Number(cam.target.x).toFixed(4),
      Number(cam.target.y).toFixed(4),
      Number(cam.target.z).toFixed(4),
    ].join('|');

    const projHit = Boolean(projectedCacheRef.current && projectedCacheRef.current.key === camKey);
    const allowProjCache = !(typeof window !== 'undefined' && (window as any).__P5_DISABLE_VOLUME_PROJ_CACHE__);
    const layerHit = Boolean(allowProjCache && staticLayerRef.current && staticLayerRef.current.key === camKey);

    const polys = timeSync('volume_project_sort', () => {
      if (allowProjCache && projectedCacheRef.current && projectedCacheRef.current.key === camKey) {
        return projectedCacheRef.current.polys;
      }
      const sorted = [...faces].sort((a, b) => a.depthKey - b.depthKey);
      const built: Array<{ pts: Array<{ u: number; v: number; depth: number }>; material: string }> = [];
      for (const face of sorted) {
        const pts = face.corners.map((c) => projectPoint(c, cam, W, H));
        if (pts.some((p) => p.depth <= 0.05)) continue;
        built.push({ pts, material: String(face.material || '') });
      }
      if (allowProjCache) {
        projectedCacheRef.current = { key: camKey, polys: built };
      }
      return built;
    }, { face_count: faces.length, cache_hit: allowProjCache && projHit });

    timeSync('volume_draw_fill', () => {
      if (layerHit && staticLayerRef.current) {
        ctx.drawImage(staticLayerRef.current.canvas, 0, 0, W, H);
        return;
      }
      // Paint static occupancy onto an offscreen layer (exact same fill/stroke), then blit.
      let layer = staticLayerRef.current?.canvas;
      if (!layer || layer.width !== canvas.width || layer.height !== canvas.height) {
        layer = document.createElement('canvas');
        layer.width = canvas.width;
        layer.height = canvas.height;
      }
      const lctx = layer.getContext('2d');
      if (!lctx) return;
      lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      lctx.fillStyle = '#12151a';
      lctx.fillRect(0, 0, W, H);
      lctx.strokeStyle = '#2a3340';
      lctx.beginPath();
      ground.forEach((p, i) => (i ? lctx.lineTo(p.u, p.v) : lctx.moveTo(p.u, p.v)));
      lctx.closePath();
      lctx.stroke();
      for (const poly of polys) {
        lctx.beginPath();
        poly.pts.forEach((p, i) => (i ? lctx.lineTo(p.u, p.v) : lctx.moveTo(p.u, p.v)));
        lctx.closePath();
        lctx.fillStyle = materialDisplayColor(poly.material);
        lctx.fill();
        lctx.strokeStyle = 'rgba(220,230,240,0.35)';
        lctx.stroke();
      }
      if (allowProjCache) {
        staticLayerRef.current = { key: camKey, canvas: layer };
      }
      ctx.drawImage(layer, 0, 0, W, H);
    }, { poly_count: polys.length, layer_hit: layerHit });

    timeSync('volume_draw_entities', () => {
      for (const b of bodies) {
        const c = b.render_center || simToRender(b.sim_x, b.sim_y, b.sim_centre_z);
        const p = projectPoint({ x: c[0], y: c[1], z: c[2] }, cam, W, H);
        if (p.depth <= 0.05) continue;
        const r = Math.max(3, (Number(b.render_radius) || 0.5) * (80 / Math.max(0.5, p.depth)));
        ctx.fillStyle = '#6ec8ff';
        ctx.beginPath();
        ctx.arc(p.u, p.v, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#d7ecff';
        ctx.font = '11px sans-serif';
        ctx.fillText(String(b.agent_id || b.body_id || 'body'), p.u + r + 2, p.v);
      }

      for (const o of objects) {
        const c = o.render_center || simToRender(o.sim_x, o.sim_y, o.sim_centre_z);
        const p = projectPoint({ x: c[0], y: c[1], z: c[2] }, cam, W, H);
        if (p.depth <= 0.05) continue;
        const r = Math.max(2, (Number(o.render_radius) || 0.25) * (70 / Math.max(0.5, p.depth)));
        ctx.fillStyle = o.held ? '#f0c35a' : '#c28bff';
        ctx.beginPath();
        ctx.arc(p.u, p.v, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }, { bodies: bodies.length, objects: objects.length });

    ctx.fillStyle = '#c9d2db';
    ctx.font = '12px sans-serif';
    ctx.fillText('RESEARCHER PHYSICAL WORLD VOLUME VIEW · NOT ORGANISM VISION', 12, 18);
    ctx.fillStyle = '#8b95a1';
    ctx.fillText(
      `volumes=${volumes.length} · bodies=${bodies.length} · objects=${objects.length} · digest=${renderDescription?.occupancy_digest || heldStaticRef.current?.occupancy_digest || '—'}`,
      12,
      34,
    );
    ctx.fillText('drag=orbit · shift+drag=pan · wheel=zoom · OBSERVER_RENDER_LIGHTING_ONLY', 12, H - 12);
    void camTick;
    void cameraEye;
  }, [available, volumes, bodies, objects, faces, tile, renderDescription, camTick, suspended, staticId, dynRev]);

  return (
    <div
      className="occupancy-volume-view"
      data-testid="occupancy-volume-view"
      data-render-suspended={suspended ? '1' : '0'}
      data-static-payload-id={staticId || ''}
      data-incremental-kind={resolved.kind}
      style={{ position: 'relative', width: '100%', height: '100%', minHeight: 360, background: '#12151a' }}
    >
      {rejectNotice ? (
        <div className="subtle" data-testid="vw7-incremental-reject" style={{ padding: 6 }}>
          VOLUME incremental rejected · {rejectNotice} · requesting full base
        </div>
      ) : null}
      <div className="subtle" data-testid="vw7-authority-label" style={{ padding: '6px 8px' }}>
        {renderDescription?.label || 'RESEARCHER PHYSICAL WORLD VOLUME VIEW'}
      </div>
      <div className="subtle" data-testid="vw7-authority" style={{ padding: '0 8px 4px' }}>
        {renderDescription?.authority || 'RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY'}
      </div>
      {!available ? (
        <div data-testid="vw7-unavailable" className="subtle" style={{ padding: 12 }}>
          VOLUME VIEW UNAVAILABLE — VW1 occupancy inactive. Does not fabricate volumetric world from heightfield.
        </div>
      ) : null}
      <canvas
        ref={ref}
        data-testid="occupancy-volume-canvas"
        style={{ width: '100%', height: 'calc(100% - 48px)', display: 'block', cursor: 'grab' }}
        onMouseDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, mode: e.shiftKey ? 'pan' : 'orbit' };
        }}
        onMouseMove={(e) => {
          if (!drag.current) return;
          const dx = e.clientX - drag.current.x;
          const dy = e.clientY - drag.current.y;
          drag.current.x = e.clientX;
          drag.current.y = e.clientY;
          const cam = camRef.current;
          if (drag.current.mode === 'orbit') {
            cam.yaw += dx * 0.01;
            cam.pitch = Math.max(-1.2, Math.min(1.35, cam.pitch + dy * 0.01));
          } else {
            cam.target.x -= dx * 0.04;
            cam.target.z += dy * 0.04;
          }
          setCamTick((t) => t + 1);
        }}
        onMouseUp={() => {
          drag.current = null;
        }}
        onMouseLeave={() => {
          drag.current = null;
        }}
        onWheel={(e) => {
          e.preventDefault();
          const cam = camRef.current;
          cam.distance = Math.max(4, Math.min(200, cam.distance * (e.deltaY > 0 ? 1.08 : 0.92)));
          setCamTick((t) => t + 1);
        }}
        onClick={() => {
          if (onSelectVolume && volumes[0]) onSelectVolume(volumes[0]);
        }}
      />
    </div>
  );
}
