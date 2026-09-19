import type { ReactNode } from 'react';
import { ToolIcon } from './icons';
import { EXPERIMENT_MENU, HOME_TOOLS, type DeviceTool, type ExperimentScreen } from './types';

type Props = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  tool: DeviceTool;
  onTool: (t: DeviceTool) => void;
  experimentScreen: ExperimentScreen;
  onExperimentScreen: (s: ExperimentScreen) => void;
  pending: boolean;
  overrideCount: number;
  undercoverInWorld: boolean;
  selectedAgentLabel: string;
  children: ReactNode;
};

export function ControlDevice({
  collapsed, onToggleCollapse, tool, onTool,
  experimentScreen, onExperimentScreen,
  pending, overrideCount, undercoverInWorld, selectedAgentLabel, children,
}: Props) {
  if (collapsed) {
    return (
      <aside className="control-device collapsed" aria-label="Control dock">
        <button type="button" className="dock-toggle" title="Expand controls" onClick={onToggleCollapse}>›</button>
        {HOME_TOOLS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`dock-icon ${tool === t.id ? 'active' : ''}`}
            title={t.label}
            onClick={() => { onTool(t.id); onToggleCollapse(); }}
          >
            <ToolIcon tool={t.id} />
          </button>
        ))}
        {pending && <span className="dock-badge" title="Pending changes">•</span>}
      </aside>
    );
  }

  return (
    <aside className="control-device expanded" aria-label="Control device">
      <header className="device-chrome">
        <button type="button" className="dock-toggle" title="Collapse" onClick={onToggleCollapse}>‹</button>
        <div className="device-chrome-meta">
          <strong>MM Control</strong>
          <span>{selectedAgentLabel}</span>
        </div>
        <div className="device-chrome-flags">
          {pending && <span className="flag pending" title="Edited config not applied">PENDING</span>}
          {overrideCount > 0 && (
            <span className="flag overrides" title="Experimental overrides active">
              OV {overrideCount}
            </span>
          )}
          <span className={`flag undercover ${undercoverInWorld ? 'in' : 'out'}`}>
            {undercoverInWorld ? 'IN' : 'OUT'}
          </span>
        </div>
      </header>

      {tool === 'home' ? (
        <nav className="device-home">
          {HOME_TOOLS.map((t) => (
            <button key={t.id} type="button" className="home-tile" onClick={() => onTool(t.id)}>
              <ToolIcon tool={t.id} />
              <span>{t.label}</span>
            </button>
          ))}
        </nav>
      ) : (
        <div className="device-screen">
          <div className="device-nav-row">
            <button type="button" className="back" onClick={() => {
              if (tool === 'experiment' && experimentScreen !== 'menu') onExperimentScreen('menu');
              else onTool('home');
            }}>
              ‹ {tool === 'experiment' && experimentScreen !== 'menu' ? 'Experiment' : 'Home'}
            </button>
            <strong className="device-screen-title">
              {tool === 'experiment' && experimentScreen !== 'menu'
                ? EXPERIMENT_MENU.find((x) => x.id === experimentScreen)?.label || 'Experiment'
                : HOME_TOOLS.find((x) => x.id === tool)?.label || tool}
            </strong>
          </div>
          {tool === 'experiment' && experimentScreen === 'menu' && (
            <nav className="device-submenu">
              {EXPERIMENT_MENU.map((s) => (
                <button key={s.id} type="button" className="submenu-row" onClick={() => onExperimentScreen(s.id)}>
                  <span>{s.label}</span><span>›</span>
                </button>
              ))}
            </nav>
          )}
          <div className="device-body">{children}</div>
        </div>
      )}
    </aside>
  );
}
