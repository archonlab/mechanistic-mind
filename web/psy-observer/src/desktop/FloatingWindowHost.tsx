import type { ReactNode } from 'react';
import { FloatingWindow } from './FloatingWindow';
import type { FloatingWindowId, FloatingWindowState } from './types';

type Props = {
  windows: FloatingWindowState[];
  bounds: { width: number; height: number };
  renderBody: (id: FloatingWindowId) => ReactNode;
  infoKind?: (id: FloatingWindowId) => 'WORLD_GT' | 'AGENT_ACCESSIBLE' | 'ANALYZER_INFERENCE' | null;
  onFocus: (id: FloatingWindowId) => void;
  onClose: (id: FloatingWindowId) => void;
  onMove: (id: FloatingWindowId, x: number, y: number) => void;
  onResize: (id: FloatingWindowId, w: number, h: number) => void;
  onMaximize: (id: FloatingWindowId) => void;
  onReset: (id: FloatingWindowId) => void;
};

export function FloatingWindowHost({
  windows, renderBody, infoKind, onFocus, onClose, onMove, onResize, onMaximize, onReset,
}: Props) {
  const ordered = [...windows].sort((a, b) => a.z - b.z);
  return (
    <div className="float-host" aria-live="polite">
      {ordered.map((win) => (
        <FloatingWindow
          key={win.id}
          win={win}
          infoKind={infoKind?.(win.id) ?? null}
          onFocus={() => onFocus(win.id)}
          onClose={() => onClose(win.id)}
          onMove={(x, y) => onMove(win.id, x, y)}
          onResize={(w, h) => onResize(win.id, w, h)}
          onMaximize={() => onMaximize(win.id)}
          onReset={() => onReset(win.id)}
        >
          {renderBody(win.id)}
        </FloatingWindow>
      ))}
    </div>
  );
}
