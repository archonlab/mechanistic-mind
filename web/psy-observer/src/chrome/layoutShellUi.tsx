import { memo, useSyncExternalStore } from 'react';
import {
  DEFAULT_LAYOUT_SHELL,
  layoutShellStore,
  layoutShellClassName,
  type LayoutShellState,
} from '../observer/layoutShell';

export function useLayoutShell(): LayoutShellState {
  return useSyncExternalStore(
    layoutShellStore.subscribe,
    layoutShellStore.get,
    () => DEFAULT_LAYOUT_SHELL,
  );
}

type ToggleProps = {
  region: 'left' | 'right' | 'bottom';
  open: boolean;
  onToggle: () => void;
  controlsId: string;
};

export const PanelCollapseToggle = memo(function PanelCollapseToggle({
  region,
  open,
  onToggle,
  controlsId,
}: ToggleProps) {
  const label = open ? `Collapse ${region} panel` : `Expand ${region} panel`;
  return (
    <button
      type="button"
      className={`shell-collapse-toggle shell-collapse-${region}`}
      data-testid={`shell-toggle-${region}`}
      aria-expanded={open}
      aria-controls={controlsId}
      title={label}
      onClick={onToggle}
    >
      <span className="shell-collapse-glyph" aria-hidden="true">
        {region === 'left' ? (open ? '‹' : '›') : region === 'right' ? (open ? '›' : '‹') : (open ? '▾' : '▴')}
      </span>
      <span className="shell-collapse-text">{region === 'left' ? 'Nav' : region === 'right' ? 'Inspector' : 'Drawer'}</span>
    </button>
  );
});

export { layoutShellClassName, layoutShellStore };
