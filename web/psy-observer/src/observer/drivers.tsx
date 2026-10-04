import { useEffect } from 'react';
import { applyObserverInterest, interestFor, syncDerivedViewportSubscription, type VolumeWorkspaceMode } from './interest';
import { clockStore, tabVisibilityStore } from './stores';
import { useStatusStore, useWorkspaceStore } from './useExternalStore';

/** 500 ms clock writes clockStore only — never App state. */
export function ClockDriver() {
  const status = useStatusStore();
  useEffect(() => {
    if (status.status !== 'RUNNING') return;
    const t = window.setInterval(() => clockStore.set(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [status.status]);
  return null;
}

/** Bind Observer presentation products to visible workspace/inspector. */
export function InterestDriver() {
  const ws = useWorkspaceStore();
  useEffect(() => {
    const plan = interestFor(ws.workspace, ws.inspector);
    void applyObserverInterest(plan);
  }, [ws.workspace, ws.inspector]);
  return null;
}

/**
 * P1: central MAP/VOLUME/SURFACE mode owns derived payload subscription.
 * Does not step/reset simulation. Preserves audio/left-dock independently.
 */
export function DerivedViewportSubscriptionDriver({ mode }: { mode: VolumeWorkspaceMode }) {
  const ws = useWorkspaceStore();
  useEffect(() => {
    void syncDerivedViewportSubscription(mode);
  }, [mode, ws.workspace, ws.inspector]);
  return null;
}

/** P1: suspend researcher render loops when the browser tab is hidden (sim continues). */
export function TabVisibilityDriver() {
  useEffect(() => {
    const sync = () => {
      tabVisibilityStore.set(Boolean(document.hidden));
    };
    sync();
    document.addEventListener('visibilitychange', sync);
    return () => document.removeEventListener('visibilitychange', sync);
  }, []);
  return null;
}

type AuxProps = {
  refreshAux: () => void;
  mode: string;
};

export function AuxPollDriver({ refreshAux, mode }: AuxProps) {
  const status = useStatusStore();
  const running = status.status === 'RUNNING' && mode === 'LIVE';
  useEffect(() => {
    if (running) return;
    if (status.tick == null) return;
    const t = window.setTimeout(() => { refreshAux(); }, 350);
    return () => window.clearTimeout(t);
  }, [running, status.tick, status.status, mode, refreshAux]);
  useEffect(() => {
    if (!running) return;
    const interval = Number(status.simulationSpeed) >= 5 ? 1500 : 2000;
    const t = window.setInterval(() => { refreshAux(); }, interval);
    return () => window.clearInterval(t);
  }, [running, status.simulationSpeed, refreshAux]);
  return null;
}
