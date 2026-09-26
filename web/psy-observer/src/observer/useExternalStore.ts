import { useCallback, useSyncExternalStore } from 'react';
import {
  clockStore,
  frameStore,
  lifecycleStore,
  statusStore,
  workspaceStore,
  type SlimStatus,
  type WorkspaceState,
} from './stores';

export function useFrameStore() {
  return useSyncExternalStore(
    frameStore.subscribe,
    () => frameStore.getVisible(),
    () => frameStore.getVisible(),
  );
}

export function useStatusStore(): SlimStatus {
  return useSyncExternalStore(statusStore.subscribe, statusStore.get, statusStore.get);
}

export function useClockStore(): number {
  return useSyncExternalStore(clockStore.subscribe, clockStore.get, clockStore.get);
}

export function useWorkspaceStore(): WorkspaceState {
  return useSyncExternalStore(workspaceStore.subscribe, workspaceStore.get, workspaceStore.get);
}

export function useLifecycleStore() {
  return useSyncExternalStore(lifecycleStore.subscribe, lifecycleStore.get, lifecycleStore.get);
}

export function useSetWorkspace() {
  return useCallback((workspace: WorkspaceState['workspace']) => {
    const cur = workspaceStore.get();
    if (cur.workspace === workspace) return;
    workspaceStore.set({
      ...cur,
      workspace,
      inspectorOpen: workspace === 'INSPECT' ? true : cur.inspectorOpen,
    });
  }, []);
}

export function useSetInspector() {
  return useCallback((inspector: WorkspaceState['inspector']) => {
    workspaceStore.set({
      ...workspaceStore.get(),
      workspace: 'INSPECT',
      inspector,
      inspectorOpen: true,
    });
  }, []);
}
