/**
 * Observer-only wall-clock RECENT side-channel HUD.
 * Primary badge remains the current published composite motor.
 *
 * Implementation lives on a const object so production bundling cannot
 * hoist-collide these helpers with later `function` declarations.
 */

export const RECENT_WINDOW_MS = 1000;

export const SIDECHANNEL_DOMAIN_ORDER = [
  'NECK',
  'OSC_EMIT',
  'OSC_FREQ',
  'OSC_AMP',
  'PUSH',
] as const;

export type SidechannelDomain = (typeof SIDECHANNEL_DOMAIN_ORDER)[number];

export const SIDECHANNEL_TOKEN_DOMAIN: Record<string, SidechannelDomain> = {
  NECK_LEFT: 'NECK',
  NECK_RIGHT: 'NECK',
  NECK_HOLD: 'NECK',
  OSC_EMIT: 'OSC_EMIT',
  OSC_FREQ_UP: 'OSC_FREQ',
  OSC_FREQ_DOWN: 'OSC_FREQ',
  OSC_AMP_UP: 'OSC_AMP',
  OSC_AMP_DOWN: 'OSC_AMP',
  PUSH: 'PUSH',
};

export type RecentSlot = { token: string; expiresAt: number };
export type AgentRecent = Partial<Record<SidechannelDomain, RecentSlot>>;

export type RecentHudStore = {
  sessionKey: string;
  ingestFingerprint: string;
  agents: Record<string, AgentRecent>;
};

export const recentHudApi = {
  empty(): RecentHudStore {
    return { sessionKey: '', ingestFingerprint: '', agents: {} };
  },

  sessionKey(frame: any): string {
    const h = frame?.header || {};
    return [
      h.runtime_generation ?? '',
      h.seed ?? '',
      h.instance_id ?? '',
    ].join('|');
  },

  tokensFrom(display: string | null | undefined): string[] {
    const raw = String(display || '').trim();
    if (!raw) return [];
    const parts = raw.split(/\s*\+\s*|\s*\|\s*/);
    const out: string[] = [];
    for (const p of parts) {
      const tok = p.trim();
      if (SIDECHANNEL_TOKEN_DOMAIN[tok]) out.push(tok);
    }
    return out;
  },

  reduce(prev: RecentHudStore, frame: any, now: number, windowMs = RECENT_WINDOW_MS): RecentHudStore {
    const sessionKey = recentHudApi.sessionKey(frame);
    const h = frame?.header || {};
    const agentsObs = frame?.agents_observer || [];
    const fp = [
      sessionKey,
      h.display_tick ?? h.frame_tick ?? h.tick ?? '',
      ...agentsObs.map((a: any, i: number) => `${a?.observer_id || a?.agent_id || i}:${a?.composite_action_display || ''}`),
    ].join('~');
    if (sessionKey === prev.sessionKey && fp === prev.ingestFingerprint) return prev;

    const agents: Record<string, AgentRecent> = sessionKey !== prev.sessionKey ? {} : {};
    if (sessionKey === prev.sessionKey) {
      for (const [id, row] of Object.entries(prev.agents)) agents[id] = { ...row };
    }
    const seen = new Set<string>();
    for (let i = 0; i < agentsObs.length; i++) {
      const a = agentsObs[i];
      const id = String(a?.observer_id || a?.agent_id || `agent_${i}`);
      seen.add(id);
      const tokens = recentHudApi.tokensFrom(a?.composite_action_display || a?.selected_action || '');
      if (!tokens.length && !agents[id]) continue;
      const row: AgentRecent = agents[id] ? { ...agents[id] } : {};
      for (const tok of tokens) {
        const domain = SIDECHANNEL_TOKEN_DOMAIN[tok];
        row[domain] = { token: tok, expiresAt: now + windowMs };
      }
      agents[id] = row;
    }
    if (agentsObs.length) {
      for (const id of Object.keys(agents)) {
        if (!seen.has(id)) delete agents[id];
      }
    }
    return { sessionKey, ingestFingerprint: fp, agents };
  },

  visible(hud: RecentHudStore, agentId: string, now: number): string[] {
    const row = hud.agents[agentId];
    if (!row) return [];
    const out: string[] = [];
    for (const domain of SIDECHANNEL_DOMAIN_ORDER) {
      const slot = row[domain];
      if (!slot) continue;
      if (slot.expiresAt <= now) continue;
      out.push(slot.token);
    }
    return out;
  },

  nextExpiry(hud: RecentHudStore, now: number): number | null {
    let min: number | null = null;
    for (const row of Object.values(hud.agents)) {
      for (const slot of Object.values(row)) {
        if (!slot) continue;
        if (slot.expiresAt > now && (min == null || slot.expiresAt < min)) min = slot.expiresAt;
      }
    }
    return min;
  },

  format(tokens: string[]): string {
    if (!tokens.length) return '';
    return `RECENT  ${tokens.join(' · ')}`;
  },
};

let store: RecentHudStore = recentHudApi.empty();

export const emptyRecentStore = (): RecentHudStore => recentHudApi.empty();
export const observerSessionKey = (frame: any): string => recentHudApi.sessionKey(frame);
export const sidechannelTokensFromComposite = (display: string | null | undefined): string[] => recentHudApi.tokensFrom(display);
export const reduceRecentSidechannels = (
  prev: RecentHudStore, frame: any, now: number, windowMs = RECENT_WINDOW_MS,
): RecentHudStore => recentHudApi.reduce(prev, frame, now, windowMs);
export const visibleRecentFrom = (hud: RecentHudStore, agentId: string, now: number): string[] => recentHudApi.visible(hud, agentId, now);
export const nextRecentExpiryFrom = (hud: RecentHudStore, now: number): number | null => recentHudApi.nextExpiry(hud, now);
export const formatRecentSidechannelLabel = (tokens: string[]): string => recentHudApi.format(tokens);

export const resetRecentSidechannelHud = (): void => {
  store = recentHudApi.empty();
};

export const ingestRecentSidechannels = (opts: {
  sessionKey: string;
  agentId: string;
  compositeDisplay: string | null | undefined;
  now: number;
  windowMs?: number;
}): void => {
  const windowMs = opts.windowMs ?? RECENT_WINDOW_MS;
  if (opts.sessionKey !== store.sessionKey) {
    store = { sessionKey: opts.sessionKey, ingestFingerprint: '', agents: {} };
  }
  const tokens = recentHudApi.tokensFrom(opts.compositeDisplay);
  if (!tokens.length && !store.agents[opts.agentId]) return;
  const agents: Record<string, AgentRecent> = {};
  for (const [id, row] of Object.entries(store.agents)) agents[id] = { ...row };
  const row: AgentRecent = agents[opts.agentId] ? { ...agents[opts.agentId] } : {};
  for (const tok of tokens) {
    const domain = SIDECHANNEL_TOKEN_DOMAIN[tok];
    row[domain] = { token: tok, expiresAt: opts.now + windowMs };
  }
  agents[opts.agentId] = row;
  store = { ...store, agents };
};

export const nextRecentExpiry = (now: number): number | null => recentHudApi.nextExpiry(store, now);

export const ingestFrameRecentSidechannels = (frame: any, now: number, windowMs = RECENT_WINDOW_MS): boolean => {
  const next = recentHudApi.reduce(store, frame, now, windowMs);
  const changed = next !== store;
  store = next;
  return changed;
};

export const visibleRecentSidechannels = (agentId: string, now: number): string[] => recentHudApi.visible(store, agentId, now);
