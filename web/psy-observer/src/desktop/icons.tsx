/** Compact SVG icons — no external icon dependency. */
import type { CSSProperties } from 'react';
import type { DeviceTool } from './types';

const base: CSSProperties = { width: 22, height: 22, stroke: 'currentColor', fill: 'none', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' };

export function ToolIcon({ tool }: { tool: DeviceTool }) {
  switch (tool) {
    case 'experiment':
      return <svg viewBox="0 0 24 24" style={base}><path d="M9 3v7l-4 8h14l-4-8V3"/><path d="M8 3h8"/></svg>;
    case 'intervention':
      return <svg viewBox="0 0 24 24" style={base}><circle cx="12" cy="8" r="3"/><path d="M5 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2"/><path d="M19 4l1 3-3 1"/></svg>;
    case 'observe':
      return <svg viewBox="0 0 24 24" style={base}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>;
    case 'sensors':
      return <svg viewBox="0 0 24 24" style={base}><path d="M4 14v4M8 10v8M12 6v12M16 10v8M20 14v4"/></svg>;
    case 'signals':
      return <svg viewBox="0 0 24 24" style={base}><path d="M2 12h4l3-7 4 14 3-7h4"/></svg>;
    case 'analyze':
      return <svg viewBox="0 0 24 24" style={base}><path d="M4 19V5M4 19h16"/><path d="M8 16l3-5 3 3 4-7"/></svg>;
    case 'runs':
      return <svg viewBox="0 0 24 24" style={base}><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>;
    case 'world_status':
      return <svg viewBox="0 0 24 24" style={base}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>;
    default:
      return <svg viewBox="0 0 24 24" style={base}><circle cx="12" cy="12" r="3"/></svg>;
  }
}
