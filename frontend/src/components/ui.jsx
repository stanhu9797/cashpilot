import { money } from "../api.js";

export function Spinner({ label = "Loading" }) {
  return (
    <span className="spinner" role="status">
      <span className="spinner-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-note" role="alert">
      <span>{error}</span>
      {onRetry && (
        <button className="link" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Amount({ value, className = "" }) {
  const v = Number(value);
  return <span className={`amount ${v > 0 ? "in" : "out"} ${className}`}>{money(v, { sign: true })}</span>;
}

const SOURCE_LABEL = { your_rule: "Your rule", rule: "Known vendor", ai: "AI", user: "You", none: "No match" };

export function Confidence({ txn }) {
  if (txn.category_source === "user") return <span className="conf conf-user">Confirmed</span>;
  const pct = Math.round(txn.confidence * 100);
  return (
    <span className={`conf ${txn.needs_review ? "conf-low" : "conf-ok"}`} title={`Categorized by: ${SOURCE_LABEL[txn.category_source] || txn.category_source}`}>
      {SOURCE_LABEL[txn.category_source] || "—"} {pct}%
    </span>
  );
}

export function CategorySelect({ value, categories, onChange, disabled, id }) {
  return (
    <select id={id} className="cat-select" value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
      {categories.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  );
}

export function AiOffNotice() {
  return (
    <div className="notice">
      AI features are off until you add an API key to the <code>.env</code> file and restart the backend. Rules-based
      categorization, imports, and the forecast still work.
    </div>
  );
}
