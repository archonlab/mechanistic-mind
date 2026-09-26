import { memo, type ReactNode } from 'react';
import { AnalyzeResultsPanel, type AnalysisSourceMode, type RunCatalogEntry } from '../components/AnalyzeResultsPanel';
import type { RunAnalysis } from '../analysis';
import { noteRender } from '../observer/stores';

type Props = {
  analysis: RunAnalysis | null;
  analyzing: boolean;
  analysisProgress?: string;
  analysisSource: AnalysisSourceMode;
  onAnalysisSourceChange: (m: AnalysisSourceMode) => void;
  savedRuns: RunCatalogEntry[];
  selectedRunId: string | null;
  onSelectRunId: (id: string | null) => void;
  onRefreshRuns: () => void;
  onAnalyze: () => void;
  onAnalyzeCurrent: () => void;
  onCopy: () => void;
  onDownload: () => void;
  onInspectTick: (t: number) => void;
  overview?: ReactNode;
};

export const AnalyzeWorkspace = memo(function AnalyzeWorkspace(props: Props) {
  noteRender('AnalyzeWorkspace');
  return (
    <div className="analyze-workspace" data-testid="workspace-analyze" data-workspace="ANALYZE">
      <div className="analyze-toolbar">
        <button type="button" className="active" onClick={props.onAnalyzeCurrent} disabled={props.analyzing}>
          Analyze Current
        </button>
        <span className="subtle">Historical evidence — not a live world dashboard. Does not follow every simulation tick.</span>
      </div>
      <div className="analyze-grid">
        <AnalyzeResultsPanel
          analysis={props.analysis}
          analyzing={props.analyzing}
          analysisProgress={props.analysisProgress}
          analysisSource={props.analysisSource}
          onAnalysisSourceChange={props.onAnalysisSourceChange}
          savedRuns={props.savedRuns}
          selectedRunId={props.selectedRunId}
          onSelectRunId={props.onSelectRunId}
          onRefreshRuns={props.onRefreshRuns}
          onAnalyze={props.onAnalyze}
          onCopy={props.onCopy}
          onDownload={props.onDownload}
          onInspectTick={props.onInspectTick}
        />
        {props.overview}
      </div>
    </div>
  );
});
