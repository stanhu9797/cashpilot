import { Component } from "react";

// Catches any rendering crash so one broken screen doesn't blank the whole app.
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("CashPilot screen error:", error, info.componentStack);
  }

  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="error-note" role="alert">
        <span>This screen hit a problem and couldn't load. Your data is safe.</span>
        <button className="link" onClick={() => this.setState({ error: null })}>Reload this screen</button>
      </div>
    );
  }
}
