import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null, errorInfo: null }; }
  componentDidCatch(error, errorInfo) { this.setState({ error, errorInfo }); }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, fontFamily: 'monospace', background: '#1e1e1e', color: '#f44', minHeight: '100vh' }}>
          <h1 style={{ color: '#f44' }}>React crashed:</h1>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#fff' }}>{this.state.error.toString()}</pre>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#aaa', fontSize: 12 }}>{this.state.errorInfo?.componentStack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  </ErrorBoundary>,
)
