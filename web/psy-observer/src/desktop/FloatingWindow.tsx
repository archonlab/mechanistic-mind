import { useCallback, useRef, useState, type ReactNode } from 'react';
import type { FloatingWindowState } from './types';

type Props = {
  win: FloatingWindowState;
  children: ReactNode;
  onFocus: () => void;
  onClose: () => void;
  onMove: (x: number, y: number) => void;
  onResize: (w: number, h: number) => void;
  onMaximize: () => void;
  onReset: () => void;
  infoKind?: 'WORLD_GT' | 'AGENT_ACCESSIBLE' | 'ANALYZER_INFERENCE' | null;
};

export function FloatingWindow({
  win, children, onFocus, onClose, onMove, onResize, onMaximize, onReset, infoKind,
}: Props) {
  const drag = useRef<{ ox: number; oy: number; sx: number; sy: number } | null>(null);
  const resize = useRef<{ ox: number; oy: number; sw: number; sh: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const onTitleDown = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    onFocus();
    drag.current = { ox: e.clientX, oy: e.clientY, sx: win.x, sy: win.y };
    setDragging(true);
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  }, [onFocus, win.x, win.y]);

  const onTitleMove = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.ox;
    const dy = e.clientY - drag.current.oy;
    onMove(drag.current.sx + dx, drag.current.sy + dy);
  }, [onMove]);

  const onTitleUp = useCallback(() => {
    drag.current = null;
    setDragging(false);
  }, []);

  const onResizeDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onFocus();
    resize.current = { ox: e.clientX, oy: e.clientY, sw: win.w, sh: win.h };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  }, [onFocus, win.w, win.h]);

  const onResizeMove = useCallback((e: React.PointerEvent) => {
    if (!resize.current) return;
    onResize(
      resize.current.sw + (e.clientX - resize.current.ox),
      resize.current.sh + (e.clientY - resize.current.oy),
    );
  }, [onResize]);

  const onResizeUp = useCallback(() => { resize.current = null; }, []);

  return (
    <div
      className={`float-window ${dragging ? 'dragging' : ''} ${win.maximized ? 'maximized' : ''}`}
      style={{ left: win.x, top: win.y, width: win.w, height: win.h, zIndex: win.z }}
      onMouseDown={onFocus}
      role="dialog"
      aria-label={win.title}
    >
      <div
        className="float-title"
        onPointerDown={onTitleDown}
        onPointerMove={onTitleMove}
        onPointerUp={onTitleUp}
      >
        <span className="float-title-text">{win.title}</span>
        {infoKind && <span className={`info-kind kind-${infoKind}`}>{infoKind.replaceAll('_', ' ')}</span>}
        <div className="float-title-actions">
          <button type="button" title="Reset position" onClick={onReset}>↺</button>
          <button type="button" title={win.maximized ? 'Restore' : 'Maximize'} onClick={onMaximize}>
            {win.maximized ? '❐' : '□'}
          </button>
          <button type="button" title="Close" onClick={onClose}>×</button>
        </div>
      </div>
      <div className="float-body">{children}</div>
      {!win.maximized && (
        <div
          className="float-resize"
          onPointerDown={onResizeDown}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeUp}
        />
      )}
    </div>
  );
}
