/** Researcher-only occupancy volume projection math (simulation → renderer).
 *
 * Transform authority:
 *   render_x = simulation_x
 *   render_y = simulation_z  (up)
 *   render_z = simulation_y  (depth)
 * Camera / lighting are OBSERVER_RENDER_LIGHTING_ONLY — not physical light.
 */

export type Vec3 = { x: number; y: number; z: number };

export const COORDINATE_TRANSFORM = {
  render_x: 'simulation_x',
  render_y: 'simulation_z',
  render_z: 'simulation_y',
  vertical_axis: 'render_y',
  lighting: 'OBSERVER_RENDER_LIGHTING_ONLY',
} as const;

export function simToRender(simX: number, simY: number, simZ: number): Vec3 {
  return { x: simX, y: simZ, z: simY };
}

export type OrbitCamera = {
  yaw: number;
  pitch: number;
  distance: number;
  target: Vec3;
};

export function defaultOrbitCamera(worldW = 32, worldH = 32): OrbitCamera {
  return {
    yaw: Math.PI * 0.25,
    pitch: Math.PI * 0.28,
    distance: Math.max(worldW, worldH) * 1.35,
    target: { x: worldW * 0.5, y: 4, z: worldH * 0.5 },
  };
}

export function cameraEye(cam: OrbitCamera): Vec3 {
  const cp = Math.cos(cam.pitch);
  const sp = Math.sin(cam.pitch);
  const cy = Math.cos(cam.yaw);
  const sy = Math.sin(cam.yaw);
  return {
    x: cam.target.x + cam.distance * cp * sy,
    y: cam.target.y + cam.distance * sp,
    z: cam.target.z + cam.distance * cp * cy,
  };
}

export function projectPoint(
  p: Vec3,
  cam: OrbitCamera,
  width: number,
  height: number,
): { u: number; v: number; depth: number } {
  const eye = cameraEye(cam);
  const fx = cam.target.x - eye.x;
  const fy = cam.target.y - eye.y;
  const fz = cam.target.z - eye.z;
  const fl = Math.hypot(fx, fy, fz) || 1;
  const fxx = fx / fl;
  const fyy = fy / fl;
  const fzz = fz / fl;
  let rx = fzz;
  let ry = 0;
  let rz = -fxx;
  const rl = Math.hypot(rx, ry, rz) || 1;
  rx /= rl;
  rz /= rl;
  const ux = ry * fzz - rz * fyy;
  const uy = rz * fxx - rx * fzz;
  const uz = rx * fyy - ry * fxx;

  const dx = p.x - eye.x;
  const dy = p.y - eye.y;
  const dz = p.z - eye.z;
  const camZ = dx * fxx + dy * fyy + dz * fzz;
  const camX = dx * rx + dy * ry + dz * rz;
  const camY = dx * ux + dy * uy + dz * uz;
  const fov = 1.1;
  const aspect = width / Math.max(1, height);
  const scale = (height * 0.5) / Math.tan(fov * 0.5);
  const denom = Math.max(0.05, camZ);
  return {
    u: width * 0.5 + (camX * scale) / denom / aspect,
    v: height * 0.5 - (camY * scale) / denom,
    depth: camZ,
  };
}

export type OccupancyPrism = {
  cell_x: number;
  cell_y: number;
  sim_x0: number;
  sim_x1: number;
  sim_y0: number;
  sim_y1: number;
  sim_z_min: number;
  sim_z_max: number;
  material_display_key?: string;
};

export function prismFaces(p: OccupancyPrism): Array<{
  corners: Vec3[];
  depthKey: number;
  material: string;
  cell_x: number;
  cell_y: number;
  z_min: number;
  z_max: number;
}> {
  const x0 = p.sim_x0;
  const x1 = p.sim_x1;
  const z0 = p.sim_z_min;
  const z1 = p.sim_z_max;
  const y0 = p.sim_y0;
  const y1 = p.sim_y1;
  const corners = [
    simToRender(x0, y0, z0),
    simToRender(x1, y0, z0),
    simToRender(x1, y1, z0),
    simToRender(x0, y1, z0),
    simToRender(x0, y0, z1),
    simToRender(x1, y0, z1),
    simToRender(x1, y1, z1),
    simToRender(x0, y1, z1),
  ];
  const facesIdx = [
    [0, 1, 2, 3],
    [4, 5, 6, 7],
    [0, 1, 5, 4],
    [2, 3, 7, 6],
    [1, 2, 6, 5],
    [0, 3, 7, 4],
  ];
  const mat = p.material_display_key || 'unknown';
  return facesIdx.map((idx) => {
    const c = idx.map((i) => corners[i]);
    const depthKey = c.reduce((s, v) => s + v.x + v.y + v.z, 0) / c.length;
    return {
      corners: c,
      depthKey,
      material: mat,
      cell_x: p.cell_x,
      cell_y: p.cell_y,
      z_min: p.sim_z_min,
      z_max: p.sim_z_max,
    };
  });
}

export function materialDisplayColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsla(${hue}, 42%, 48%, 0.72)`;
}

export function assertNoSolidFillAcrossGap(
  volumes: OccupancyPrism[],
  cellX: number,
  cellY: number,
  freeLo: number,
  freeHi: number,
): boolean {
  for (const v of volumes) {
    if (v.cell_x !== cellX || v.cell_y !== cellY) continue;
    if (v.sim_z_max > freeLo + 1e-12 && v.sim_z_min < freeHi - 1e-12) {
      if (v.sim_z_min >= freeHi - 1e-12 || v.sim_z_max <= freeLo + 1e-12) continue;
      return false;
    }
  }
  return true;
}
