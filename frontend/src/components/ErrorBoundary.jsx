import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px', color: '#fff', textAlign: 'center', fontFamily: 'system-ui, sans-serif' }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#ff6b6b', fontWeight: 'bold' }}>{this.state.error?.message || 'Unknown error'}</p>
          {this.state.error?.stack && (
            <pre style={{
              textAlign: 'left',
              background: 'rgba(0,0,0,0.5)',
              padding: '12px',
              borderRadius: '6px',
              fontSize: '12px',
              maxWidth: '600px',
              margin: '16px auto',
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
            }}>
              {this.state.error.stack}
            </pre>
          )}
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              marginTop: '16px',
              padding: '8px 16px',
              background: '#2f3fb8',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

