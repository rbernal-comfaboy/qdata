import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
        <p className="text-red-300 font-semibold mb-1">Error inesperado en la interfaz</p>
        <pre className="text-xs text-red-200 font-mono whitespace-pre-wrap break-all">
          {this.state.error.message}
          {'\n\n'}
          {this.state.error.stack}
        </pre>
        <button
          onClick={() => this.setState({ error: null })}
          className="mt-3 text-xs px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
        >
          Reintentar
        </button>
      </div>
    )
  }
}