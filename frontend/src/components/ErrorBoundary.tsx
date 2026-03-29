import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--app-bg)' }}>
          <div className="text-center p-8 rounded-2xl" style={{ background: 'var(--panel-bg)', border: '1px solid var(--panel-border)' }}>
            <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
              エラーが発生しました
            </h2>
            <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
              {this.state.error?.message}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              className="px-4 py-2 rounded-lg text-white font-medium"
              style={{ background: 'var(--accent)' }}
            >
              リロード
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
