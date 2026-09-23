import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode };
type State = { error: Error | null };

/** Keeps CSS shell visible if a child throws; optional panels must not blank #root. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Psy Observer render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="loading" style={{ padding: 24, textAlign: 'left', maxWidth: 720, margin: '0 auto' }}>
          <h2 style={{ color: 'var(--red, #fb7185)', marginTop: 0 }}>Observer UI error</h2>
          <p className="subtle">A render exception prevented the desktop shell. Fix the cause and reload.</p>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: 'var(--amber, #f2b84b)' }}>
            {this.state.error.message}
          </pre>
          <button type="button" onClick={() => this.setState({ error: null })}>
            Retry render
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
