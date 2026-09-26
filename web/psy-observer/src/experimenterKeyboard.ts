/**
 * BETA2-INT-01.1 — Experimenter keyboard routing (Observer UI only).
 *
 * Single authoritative hotkey map + focus/modifier safety.
 * Listener is installed once at App shell level — not per-tab.
 */

export const EXPERIMENTER_KEY_MAP: Record<string, { kind: string; action?: string }> = {
  KeyW: { kind: 'ACTION', action: 'MOVE:N' },
  KeyS: { kind: 'ACTION', action: 'MOVE:S' },
  KeyA: { kind: 'ACTION', action: 'MOVE:W' },
  KeyD: { kind: 'ACTION', action: 'MOVE:E' },
  Space: { kind: 'ACTION', action: 'WAIT' },
  KeyQ: { kind: 'FIELD_A' },
  KeyE: { kind: 'FIELD_B' },
};

/** Min wall-clock gap between identical commands (key-repeat / burst suppression). */
export const EXPERIMENTER_CMD_DEBOUNCE_MS = 80;

export type ExperimenterHotkeyDecision =
  | { handle: false; reason: string }
  | { handle: true; kind: string; action?: string };

export function isTypingFocusTarget(target: EventTarget | null): boolean {
  if (!target || typeof target !== 'object') return false;
  const el = target as {
    tagName?: string;
    isContentEditable?: boolean;
    closest?: (sel: string) => unknown;
  };
  const tag = String(el.tagName || '').toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.isContentEditable) return true;
  if (typeof el.closest === 'function') {
    try {
      if (el.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]')) {
        return true;
      }
    } catch {
      /* non-DOM test doubles */
    }
  }
  return false;
}

export function hasBlockingModifier(ev: { ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }): boolean {
  return !!(ev.ctrlKey || ev.metaKey || ev.altKey);
}

/**
 * Decide whether a keydown should become an experimenter command.
 * Pure — used by the global listener and unit tests.
 */
export function decideExperimenterHotkey(
  ev: {
    code: string;
    repeat?: boolean;
    ctrlKey?: boolean;
    metaKey?: boolean;
    altKey?: boolean;
    target?: EventTarget | null;
  },
  opts: { controlActive: boolean },
): ExperimenterHotkeyDecision {
  if (!opts.controlActive) {
    return { handle: false, reason: 'no_experimenter_body' };
  }
  if (ev.repeat) {
    return { handle: false, reason: 'key_repeat' };
  }
  if (hasBlockingModifier(ev)) {
    return { handle: false, reason: 'modifier_shortcut' };
  }
  if (isTypingFocusTarget(ev.target ?? null)) {
    return { handle: false, reason: 'typing_focus' };
  }
  const map = EXPERIMENTER_KEY_MAP[ev.code];
  if (!map) {
    return { handle: false, reason: 'unmapped' };
  }
  return { handle: true, kind: map.kind, action: map.action };
}

/** Debounce gate for identical command keys. */
export function shouldAcceptDebounced(
  lastByKey: Record<string, number>,
  cmdKey: string,
  nowMs: number,
  debounceMs: number = EXPERIMENTER_CMD_DEBOUNCE_MS,
): boolean {
  const last = lastByKey[cmdKey] || 0;
  if (nowMs - last < debounceMs) return false;
  lastByKey[cmdKey] = nowMs;
  return true;
}

export function experimenterControlActive(status: string | null | undefined): boolean {
  return status === 'CONTROL_ACTIVE';
}
