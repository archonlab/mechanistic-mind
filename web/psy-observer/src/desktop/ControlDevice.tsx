import { ToolIcon } from './icons';
import { HOME_TOOLS, type DeviceTool, type ExperimentScreen } from './types';

type Props = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  tool: DeviceTool;
  activeTool?: DeviceTool | null;
  onTool: (t: DeviceTool) => void;
  experimentScreen: ExperimentScreen;
  onExperimentScreen: (s: ExperimentScreen) => void;
  pending: boolean;
  overrideCount: number;
  undercoverInWorld: boolean;
  selectedAgentLabel: string;
};

export function ControlDevice({
  collapsed, onToggleCollapse, tool, activeTool, onTool,
  experimentScreen: _experimentScreen, onExperimentScreen: _onExperimentScreen,
  pending, overrideCount, undercoverInWorld, selectedAgentLabel,
}: Props) {
  void _experimentScreen;
  void _onExperimentScreen;
  if (collapsed) {
    return (
      <aside className="control-device collapsed" aria-label="Control dock">
        <button type="button" className="dock-toggle" title="Expand controls" onClick={onToggleCollapse}>›</button>
        {HOME_TOOLS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`dock-icon ${(activeTool === undefined ? tool : activeTool) === t.id ? 'active' : ''}`}
            title={t.label}
            data-rail-tool={t.id}
            onClick={() => { onTool(t.id); }}
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

      <nav className="device-home">
        {HOME_TOOLS.map((t) => (
          <button key={t.id} type="button" className={`home-tile ${(activeTool === undefined ? tool : activeTool) === t.id ? 'active' : ''}`} onClick={() => onTool(t.id)}>
            <ToolIcon tool={t.id} />
            <span>{t.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
