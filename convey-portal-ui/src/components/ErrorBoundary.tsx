import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught:', error, info);
  }

  handleRefresh = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          background: '#F7F6F3',
          color: '#3D3730',
          fontFamily: '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
          padding: '24px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, margin: '0 0 8px', letterSpacing: '-0.3px' }}>
            出了点问题
          </h1>
          <p style={{ fontSize: '14px', color: '#8A847C', margin: '0 0 24px', lineHeight: 1.5, maxWidth: '320px' }}>
            应用遇到了意外错误，请尝试刷新页面。
          </p>
          <button
            onClick={this.handleRefresh}
            style={{
              padding: '12px 28px',
              borderRadius: '10px',
              border: 'none',
              background: '#FF9F43',
              color: '#fff',
              fontSize: '15px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#F28B2E'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = '#FF9F43'; }}
          >
            刷新页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
