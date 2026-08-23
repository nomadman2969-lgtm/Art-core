import React from "react";
import { Link } from "react-router-dom";

/** Global error boundary — prevents any uncaught render error from white-screening the app. */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Art Core UI error:", error, info);
  }
  reset = () => this.setState({ hasError: false, error: null });
  render() {
    if (this.state.hasError) {
      return (
        <div data-testid="error-boundary" className="min-h-screen bg-[#0A0A0C] text-white flex items-center justify-center px-6">
          <div className="max-w-lg text-center">
            <div className="label-caps text-[#FF4D4D]">Something broke</div>
            <h1 className="font-anton text-6xl uppercase mt-4 leading-none">Hit a wall.</h1>
            <p className="text-zinc-400 mt-6">The gallery hit a snag. Try reloading, or head back to the entrance.</p>
            <div className="flex flex-wrap gap-3 justify-center mt-8">
              <button onClick={() => window.location.reload()} data-testid="err-reload" className="btn-lime">Reload</button>
              <Link to="/" onClick={this.reset} data-testid="err-home" className="btn-ghost">Back Home</Link>
            </div>
            {process.env.NODE_ENV === "development" && this.state.error && (
              <pre className="mt-8 text-left text-xs text-zinc-500 bg-black/50 p-4 rounded-sm overflow-auto max-h-64">{String(this.state.error?.stack || this.state.error)}</pre>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
