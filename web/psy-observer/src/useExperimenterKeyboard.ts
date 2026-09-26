/**
 * Global ExperimenterController keyboard hook — App shell only.
 * Exactly one listener; INTERACT must not install a second.
 */
import { useEffect, useRef, useState } from 'react';
import { experimenterCommand } from './api/client';
import {
  decideExperimenterHotkey,
  experimenterControlActive,
  shouldAcceptDebounced,
} from './experimenterKeyboard';

export function useExperimenterKeyboard(opts: {
  /** From live frame experimenter_interaction.status */
  status?: string | null;
  enabled?: boolean;
}) {
  const active = experimenterControlActive(opts.status) && opts.enabled !== false;
  const activeRef = useRef(active);
  activeRef.current = active;
  const lastCmdTick = useRef<Record<string, number>>({});
  const [pressed, setPressed] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    function onDown(ev: KeyboardEvent) {
      const decision = decideExperimenterHotkey(ev, {
        controlActive: activeRef.current,
      });
      if (!decision.handle) return;
      const cmdKey = `${decision.kind}:${decision.action || ''}`;
      if (!shouldAcceptDebounced(lastCmdTick.current, cmdKey, performance.now())) {
        return;
      }
      ev.preventDefault();
      setPressed(decision.action || decision.kind);
      void experimenterCommand({
        kind: decision.kind,
        action: decision.action,
      }).then((out) => {
        if (!out?.accepted) setLastError(String(out?.error || 'command rejected'));
        else setLastError(null);
      }).catch((e) => setLastError(String(e)));
    }
    function onUp(ev: KeyboardEvent) {
      // Clear pressed display when any mapped key lifts
      if (ev.code.startsWith('Key') || ev.code === 'Space') {
        setPressed(null);
      }
    }
    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
    };
  }, []); // install once — active gated via ref

  return { active, pressed, lastError };
}
