/** Collapsible left sensory dock: VISION (FPV) | HEARING. UI state only. */

import { useEffect, useRef, useState } from 'react';
import { useSyncExternalStore } from 'react';
import { TiktaalikEyePanel, type EyeLayout } from './TiktaalikEyePanel';
import {
  inspectorUiStore,
  type EyeDockMode,
  type LeftSensoryMode,
} from '../observer/stores';
import { HearingWorkspacePanel } from '../acoustic/HearingWorkspacePanel.tsx';
import {
  getListeningModeOwner,
  subscribeListeningMode,
} from '../acoustic/listeningModeOwner.ts';
import { getRegisteredC1Engine } from '../acoustic/c1EngineBridge.ts';
import { getRegisteredSav2Engine } from '../acoustic/sav2EngineBridge.ts';
import {
  hearingIndicatorLabel,
  listeningIsActive,
} from '../acoustic/hearingActiveStatus.ts';
import { syncEyeDockDualFpvSubscription } from '../observer/interest';
import { wantEyeDockDualFpvSubscription } from './eyeDockDualFpvLifecycle';

const EYE_PREFS_KEY = 'mm.observer.eyeDock';
const NORMAL_W = 400;
const WIDE_W = 600;
const MIN_W = 320;
const MAX_W = 680;

function loadEyePrefs(): {
  mode?: EyeDockMode;
  width?: number;
  layout?: EyeLayout;
  sensory?: LeftSensoryMode;
} {
  try {
    return JSON.parse(localStorage.getItem(EYE_PREFS_KEY) || '{}') || {};
  } catch {
    return {};
  }
}

export function TiktaalikEyeDock({
  frame,
  executionMode,
  paused,
  runtimeGeneration,
  selectedCell,
  centralOwnsSensory = null,
  agentCount = 2,
  selectedAgentId = 'agent_0',
  onSelectAgent,
  onOpenDetailedFpv,
  onEditVisionConfig,
  onOpenDetailedHearing,
}: {
  frame?: any;
  executionMode?: string;
  paused?: boolean;
  runtimeGeneration?: number | null;
  selectedCell?: any;
  /** When observation destination owns Vision/Hearing center, suppress duplicate panel. */
  centralOwnsSensory?: 'VISION' | 'HEARING' | null;
  agentCount?: number;
  selectedAgentId?: string;
  onSelectAgent?: (index: number) => void;
  onOpenDetailedFpv?: (index: number) => void;
  onEditVisionConfig?: () => void;
  onOpenDetailedHearing?: () => void;
}) {
  const ui = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const drag = useRef<{ startX: number; startW: number } | null>(null);
  const [, bump] = useState(0);
  useEffect(() => subscribeListeningMode(() => bump((n) => n + 1)), []);

  useEffect(() => {
    const p = loadEyePrefs();
    const cur = inspectorUiStore.get();
    inspectorUiStore.set({
      ...cur,
      eyeDockMode: p.mode === 'NORMAL' || p.mode === 'WIDE' || p.mode === 'CLOSED' ? p.mode : cur.eyeDockMode,
      eyeDockWidth: Number.isFinite(Number(p.width)) ? Math.max(MIN_W, Math.min(MAX_W, Number(p.width))) : cur.eyeDockWidth,
      eyeLayout: p.layout === 'A0' || p.layout === 'A1' || p.layout === 'SPLIT' ? p.layout : (cur.eyeLayout === 'A0' || cur.eyeLayout === 'A1' || cur.eyeLayout === 'SPLIT' ? cur.eyeLayout : 'A0'),
      leftSensoryMode: p.sensory === 'HEARING' || p.sensory === 'VISION' ? p.sensory : (cur.leftSensoryMode || 'VISION'),
    });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(EYE_PREFS_KEY, JSON.stringify({
        mode: ui.eyeDockMode,
        width: ui.eyeDockWidth,
        layout: ui.eyeLayout,
        sensory: ui.leftSensoryMode,
      }));
    } catch { /* ignore */ }
  }, [ui.eyeDockMode, ui.eyeDockWidth, ui.eyeLayout, ui.leftSensoryMode]);

  const mode = ui.eyeDockMode;
  const open = mode !== 'CLOSED';
  const sensory: LeftSensoryMode = ui.leftSensoryMode === 'HEARING' ? 'HEARING' : 'VISION';
  const width = mode === 'WIDE' ? Math.max(WIDE_W, ui.eyeDockWidth) : mode === 'NORMAL' ? Math.max(MIN_W, Math.min(WIDE_W - 1, ui.eyeDockWidth || NORMAL_W)) : 22;

  // Dual exact FPV delivery is dock-owned, not Vision-subtab-owned.
  // Hearing playback must not disable latest_exact_by_agent; Vision may suspend paint only.
  // Do not POST enabled:false from effect cleanup — that races StrictMode remounts
  // and destination switches, leaving the packaged API without the dual map.
  useEffect(() => {
    const want = wantEyeDockDualFpvSubscription({ open, centralOwnsSensory });
    void syncEyeDockDualFpvSubscription(want);
  }, [open, centralOwnsSensory]);

  const owner = getListeningModeOwner();
  const active = listeningIsActive(owner);
  const eng = owner === 'PHYSICAL_FIELD_C1' ? getRegisteredC1Engine() : owner === 'SELECTED_ORGANISM_SAV2' ? getRegisteredSav2Engine() : null;
  const muted = !!eng?.snapshot()?.muted;
  const indicator = hearingIndicatorLabel({ owner, muted });

  function setMode(next: EyeDockMode) {
    inspectorUiStore.set({
      ...inspectorUiStore.get(),
      eyeDockMode: next,
      eyeDockWidth: next === 'WIDE' ? WIDE_W : next === 'NORMAL' ? NORMAL_W : inspectorUiStore.get().eyeDockWidth,
    });
  }

  function setSensory(next: LeftSensoryMode) {
    inspectorUiStore.set({ ...inspectorUiStore.get(), leftSensoryMode: next });
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

  function quickMuteToggle() {
    const o = getListeningModeOwner();
    if (o === 'PHYSICAL_FIELD_C1') {
      const e = getRegisteredC1Engine();
      if (e) e.setMute(!e.snapshot().muted);
    } else if (o === 'SELECTED_ORGANISM_SAV2') {
      const e = getRegisteredSav2Engine();
      if (e) e.setMute(!e.snapshot().muted);
    }
    bump((n) => n + 1);
  }

  const showVision = open && sensory === 'VISION' && centralOwnsSensory !== 'VISION';
  const showHearing = open && sensory === 'HEARING' && centralOwnsSensory !== 'HEARING';
  const keepHearingMounted = centralOwnsSensory !== 'HEARING';
  const keepVisionMounted = centralOwnsSensory !== 'VISION';
  const exec = String(executionMode || 'LIVE');
  const pause = !!paused;
  const gen = runtimeGeneration != null ? Number(runtimeGeneration) : null;
  const visionSuspended = !showVision;

  return (
    <aside
      className={`eye-side-dock ${mode.toLowerCase()}`}
      data-testid="tiktaalik-eye-dock"
      data-mode={mode}
      data-sensory={sensory}
      style={{ width }}
      aria-label="Left sensory dock — Vision and Hearing"
    >
      {open ? (
        <div className="eye-side-dock-head">
          <button type="button" className={mode === 'NORMAL' ? 'active' : ''} onClick={() => setMode('NORMAL')}>NORMAL</button>
          <button type="button" className={mode === 'WIDE' ? 'active' : ''} onClick={() => setMode('WIDE')}>WIDE</button>
          <button type="button" title="Close left sensory dock (does not stop listening)" onClick={() => setMode('CLOSED')}>CLOSE</button>
          <span className="eye-sensory-tabs" data-testid="left-sensory-tabs">
            <button
              type="button"
              data-testid="left-sensory-vision"
              className={sensory === 'VISION' ? 'active' : ''}
              onClick={() => setSensory('VISION')}
            >
              VISION
            </button>
            <button
              type="button"
              data-testid="left-sensory-hearing"
              className={sensory === 'HEARING' ? 'active' : ''}
              onClick={() => setSensory('HEARING')}
            >
              HEARING
            </button>
          </span>
          <span
            className="hearing-active-indicator"
            data-testid="hearing-active-indicator"
            data-kind={indicator}
            title="Active listening status (does not create a second engine)"
          >
            {active ? indicator : 'HEARING · OFF'}
          </span>
          {active ? (
            <button
              type="button"
              data-testid="hearing-quick-mute"
              title="Mute/unmute active listening"
              onClick={quickMuteToggle}
            >
              {muted ? 'UNMUTE' : 'MUTE'}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="eye-side-dock-closed-stack">
          <button
            type="button"
            className="eye-side-dock-handle"
            title="Open Vision / Hearing dock"
            data-testid="left-sensory-closed-open"
            onClick={() => setMode('NORMAL')}
          >
            EYE
          </button>
          {active ? (
            <>
              <button
                type="button"
                className="eye-side-dock-handle hearing-closed-indicator"
                data-testid="hearing-active-indicator-closed"
                title={indicator}
                onClick={() => {
                  setSensory('HEARING');
                  setMode('NORMAL');
                }}
              >
                HEAR
              </button>
              <button
                type="button"
                className="eye-side-dock-handle"
                data-testid="hearing-quick-mute"
                title={muted ? 'Unmute' : 'Mute'}
                onClick={quickMuteToggle}
              >
                {muted ? 'U' : 'M'}
              </button>
            </>
          ) : null}
        </div>
      )}

      <div
        className="eye-side-dock-body"
        data-testid="left-sensory-body"
        style={{ display: open ? undefined : 'none' }}
        aria-hidden={!open}
      >
        <div
          data-testid="left-vision-workspace"
          style={{ display: showVision ? undefined : 'none' }}
          aria-hidden={!showVision}
        >
          {keepVisionMounted ? (
            <TiktaalikEyePanel
              layout={ui.eyeLayout === 'A1' || ui.eyeLayout === 'SPLIT' ? ui.eyeLayout : 'A0'}
              onLayout={onLayout}
              captureEnabled
              dockWide={mode === 'WIDE'}
              dockHidden={visionSuspended}
              agentCount={agentCount}
              selectedAgentId={selectedAgentId}
              onSelectAgent={onSelectAgent}
              onOpenDetailedFpv={onOpenDetailedFpv}
              onEditVisionConfig={onEditVisionConfig}
            />
          ) : null}
        </div>
        <div
          data-testid="left-hearing-workspace-host"
          style={{ display: showHearing ? undefined : 'none' }}
          aria-hidden={!showHearing}
        >
          {keepHearingMounted ? (
            <HearingWorkspacePanel
              frame={frame}
              executionMode={exec}
              paused={pause}
              runtimeGeneration={gen}
              selectedCell={selectedCell}
              compact
              dockVisible={showHearing}
              onOpenDetailed={onOpenDetailedHearing}
            />
          ) : null}
        </div>
      </div>

      {open ? (
        <div className="eye-side-dock-resizer" onMouseDown={onResizeStart} title="Resize sensory dock" />
      ) : null}
    </aside>
  );
}
