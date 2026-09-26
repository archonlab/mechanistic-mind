/** Theme-specific WORLD canvas presentation. Scientific class/agent/FOV geometry unchanged. */

export type WorldChrome = {
  stage: string;
  veil: string;
  grid: string;
  annotate: string;
  annotateMuted: string;
  annotateWarn: string;
  annotateOk: string;
  wrap: string;
  wrapLabel: string;
  trajectory: string;
  trajectoryHi: string;
  vector: string;
  fontUi: string;
  fontMono: string;
  classColors: string[];
  fov: Array<{ fill: string; stroke: string; label: string }>;
};

const DARK: WorldChrome = {
  stage: '#070b10',
  veil: 'rgba(7,11,16,0.55)',
  grid: 'rgba(255,255,255,0.06)',
  annotate: '#e2e8f0',
  annotateMuted: '#94a3b8',
  annotateWarn: '#f59e0b',
  annotateOk: '#22c55e',
  wrap: 'rgba(56,189,248,0.55)',
  wrapLabel: 'rgba(56,189,248,0.8)',
  trajectory: 'rgba(96,165,250,0.85)',
  trajectoryHi: 'rgba(147,197,253,0.95)',
  vector: 'rgba(226,232,240,0.75)',
  fontUi: '12px Inter, ui-sans-serif, system-ui, sans-serif',
  fontMono: '11px "SFMono-Regular", Consolas, "Liberation Mono", monospace',
  classColors: [
    'rgba(15,23,42,0)',
    'rgba(100,116,139,0.45)',
    'rgba(34,197,94,0.55)',
    'rgba(245,158,11,0.50)',
    'rgba(249,115,22,0.58)',
    'rgba(239,68,68,0.65)',
  ],
  fov: [
    { fill: 'rgba(56, 189, 248, 0.14)', stroke: 'rgba(56, 189, 248, 0.65)', label: '#7dd3fc' },
    { fill: 'rgba(251, 146, 60, 0.14)', stroke: 'rgba(249, 115, 22, 0.7)', label: '#fdba74' },
    { fill: 'rgba(167, 139, 250, 0.14)', stroke: 'rgba(139, 92, 246, 0.7)', label: '#c4b5fd' },
    { fill: 'rgba(52, 211, 153, 0.12)', stroke: 'rgba(16, 185, 129, 0.7)', label: '#6ee7b7' },
  ],
};

const LIGHT: WorldChrome = {
  stage: '#d4dce6',
  veil: 'rgba(228,233,240,0.62)',
  grid: 'rgba(32,48,64,0.14)',
  annotate: '#1a2330',
  annotateMuted: '#4a5b6e',
  annotateWarn: '#a15c12',
  annotateOk: '#157a48',
  wrap: 'rgba(14,116,166,0.65)',
  wrapLabel: 'rgba(14,90,130,0.92)',
  trajectory: 'rgba(29, 78, 176, 0.88)',
  trajectoryHi: 'rgba(30, 64, 175, 0.95)',
  vector: 'rgba(30, 45, 62, 0.55)',
  fontUi: '12px Inter, ui-sans-serif, system-ui, sans-serif',
  fontMono: '11px "SFMono-Regular", Consolas, "Liberation Mono", monospace',
  classColors: [
    'rgba(212,220,230,0)',
    'rgba(100,116,139,0.38)',
    'rgba(22,163,74,0.48)',
    'rgba(217,119,6,0.48)',
    'rgba(234,88,12,0.52)',
    'rgba(220,38,38,0.55)',
  ],
  fov: [
    { fill: 'rgba(2, 132, 199, 0.18)', stroke: 'rgba(3, 105, 161, 0.85)', label: '#0c4a6e' },
    { fill: 'rgba(234, 88, 12, 0.18)', stroke: 'rgba(194, 65, 12, 0.88)', label: '#7c2d12' },
    { fill: 'rgba(124, 58, 237, 0.16)', stroke: 'rgba(91, 33, 182, 0.85)', label: '#4c1d95' },
    { fill: 'rgba(5, 150, 105, 0.16)', stroke: 'rgba(4, 120, 87, 0.85)', label: '#064e3b' },
  ],
};

export function resolvedWorldTheme(root: { dataset?: DOMStringMap } | null | undefined): 'light' | 'dark' {
  return root?.dataset?.theme === 'light' ? 'light' : 'dark';
}

export function worldChrome(theme: 'light' | 'dark' = 'dark'): WorldChrome {
  return theme === 'light' ? LIGHT : DARK;
}
