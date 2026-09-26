/** Collapsible left Tiktaalik Eye dock. UI state only. */

import { useEffect, useRef } from 'react';
import { useSyncExternalStore } from 'react';
import { TiktaalikEyePanel, type EyeLayout } from './TiktaalikEyePanel';
import { inspectorUiStore, type EyeDockMode } from '../observer/stores';

const EYE_PREFS_KEY = 'mm.observer.eyeDock';
const NORMAL_W = 400;
const WIDE_W = 600;
const MIN_W = 320;
const MAX_W = 680;

function loadEyePrefs(): { mode?: EyeDockMode; width?: number; layout?: EyeLayout } {
  try {
    return JSON.parse(localStorage.getItem(EYE_PREFS_KEY) || '{}') || {};
  } catch {
    return {};
  }
}

export function TiktaalikEyeDock() {
  const ui = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const drag = useRef<{ startX: number; startW: number } | null>(null);

  useEffect(() => {
    const p = loadEyePrefs();
    const cur = inspectorUiStore.get();
    inspectorUiStore.set({
      ...cur,
      eyeDockMode: p.mode === 'NORMAL' || p.mode === 'WIDE' || p.mode === 'CLOSED' ? p.mode : cur.eyeDockMode,
      eyeDockWidth: Number.isFinite(Number(p.width)) ? Math.max(MIN_W, Math.min(MAX_W, Number(p.width))) : cur.eyeDockWidth,
      eyeLayout: p.layout === 'A0' || p.layout === 'A1' || p.layout === 'SPLIT' ? p.layout : (cur.eyeLayout === 'A0' || cur.eyeLayout === 'A1' || cur.eyeLayout === 'SPLIT' ? cur.eyeLayout : 'A0'),
    });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(EYE_PREFS_KEY, JSON.stringify({
        mode: ui.eyeDockMode,
        width: ui.eyeDockWidth,
        layout: ui.eyeLayout,
      }));
    } catch { /* ignore */ }
  }, [ui.eyeDockMode, ui.eyeDockWidth, ui.eyeLayout]);

  const mode = ui.eyeDockMode;
  const open = mode !== 'CLOSED';
  const width = mode === 'WIDE' ? Math.max(WIDE_W, ui.eyeDockWidth) : mode === 'NORMAL' ? Math.max(MIN_W, Math.min(WIDE_W - 1, ui.eyeDockWidth || NORMAL_W)) : 22;

  function setMode(next: EyeDockMode) {
    inspectorUiStore.set({
      ...inspectorUiStore.get(),
      eyeDockMode: next,
      eyeDockWidth: next === 'WIDE' ? WIDE_W : next === 'NORMAL' ? NORMAL_W : inspectorUiStore.get().eyeDockWidth,
    });
  }

  function onLayout(l: EyeLayout) {
    inspectorUiStore.set({ ...inspectorUiStore.get(), eyeLayout: l });
  }

  function onResizeStart(ev: React.MouseEvent) {
    if (!open) return;
    ev.preventDefault();
    drag.current = { startX: ev.clientX, startW: width };
    const move = (e: MouseEvent) => {
      if (!drag.current) return;
      const w = Math.max(MIN_W, Math.min(MAX_W, drag.current.startW + (e.clientX - drag.current.startX)));
      inspectorUiStore.set({
        ...inspectorUiStore.get(),
        eyeDockWidth: w,
        eyeDockMode: w >= 540 ? 'WIDE' : 'NORMAL',
      });
    };
    const up = () => {
      drag.current = null;
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  }

  return (
    <aside
      className={`eye-side-dock ${mode.toLowerCase()}`}
      data-testid="tiktaalik-eye-dock"
      data-mode={mode}
      style={{ width }}
      aria-label="Tiktaalik Eye dock"
    >
      {open ? (
        <>
          <div className="eye-side-dock-head">
            <button type="button" className={mode === 'NORMAL' ? 'active' : ''} onClick={() => setMode('NORMAL')}>NORMAL</button>
            <button type="button" className={mode === 'WIDE' ? 'active' : ''} onClick={() => setMode('WIDE')}>WIDE</button>
            <button type="button" title="Close Eye dock" onClick={() => setMode('CLOSED')}>CLOSE</button>
          </div>
          <div className="eye-side-dock-body">
            <TiktaalikEyePanel
              layout={ui.eyeLayout === 'A1' || ui.eyeLayout === 'SPLIT' ? ui.eyeLayout : 'A0'}
              onLayout={onLayout}
              captureEnabled
            />
          </div>
          <div className="eye-side-dock-resizer" onMouseDown={onResizeStart} title="Resize Eye dock" />
        </>
      ) : (
        <button
          type="button"
          className="eye-side-dock-handle"
          title="Open Tiktaalik Eye"
          onClick={() => setMode('NORMAL')}
        >
          EYE
        </button>
      )}
    </aside>
  );
}
