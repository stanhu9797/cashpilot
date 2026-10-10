import { useEffect, useState } from "react";
import { api, money } from "../api.js";
import { AiOffNotice, ErrorNote, Spinner } from "../components/ui.jsx";

export default function Overview({ go, user }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = () => {
    setError("");
    api("/api/dashboard").then(setData).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  if (error) return <ErrorNote error={error} onRetry={load} />;
  if (!data) return <Spinner label="Loading your month" />;

  const maxCat = Math.max(1, ...data.top_categories.map((c) => c.total));
  const firstName = (user.name || "").split(" ")[0];

  return (
    <div className="page">
      <header className="page-head">
        <h1>{firstName ? `${firstName}'s books` : "Your books"}, {data.month_label}</h1>
      </header>

      {data.demo_mode && (
        <div className="notice">This is a live demo. Changes you make reset whenever the app restarts.</div>
      )}
      {!data.ai_available && <AiOffNotice />}

      {data.needs_review > 0 ? (
        <button className="review-strip" onClick={() => go("transactions?review")}>
          <span className="hl">{data.needs_review} {data.needs_review === 1 ? "transaction needs" : "transactions need"} a quick check</span>
          <span className="review-strip-cta">Review now</span>
        </button>
      ) : data.transaction_count > 0 ? (
        <div className="all-clear">Everything is categorized and confirmed.</div>
      ) : null}

      {data.transaction_count === 0 ? (
        <section className="empty">
          <h2>Start with your bank file or a receipt</h2>
          <p>Export the last 90 days as a CSV from your bank's website, or snap a photo of a receipt.</p>
          <div className="row">
            <button className="btn btn-primary" onClick={() => go("transactions")}>Import bank CSV</button>
            <button className="btn" onClick={() => go("receipt")}>Add a receipt</button>
          </div>
        </section>
      ) : (
        <>
          <section className="ledger-totals" aria-label="This month">
            <div>
              <span className="lt-label">Money in</span>
              <span className="lt-value in">{money(data.money_in, { cents: false })}</span>
            </div>
            <div>
              <span className="lt-label">Money out</span>
              <span className="lt-value out">{money(data.money_out, { cents: false })}</span>
            </div>
            <div className="lt-net">
              <span className="lt-label">Net this month</span>
              <span className={`lt-value ${data.net >= 0 ? "in" : "out"}`}>{money(data.net, { cents: false, sign: true })}</span>
            </div>
          </section>

          <section className="panel">
            <h2>Where it went this month</h2>
            {data.top_categories.length === 0 ? (
              <p className="muted">No spending yet this month.</p>
            ) : (
              <ul className="bars">
                {data.top_categories.map((c) => (
                  <li key={c.category}>
                    <span className="bar-label">{c.category}</span>
                    <span className="bar-track">
                      <span className="bar-fill" style={{ width: `${(c.total / maxCat) * 100}%` }} />
                    </span>
                    <span className="bar-value">{money(c.total, { cents: false })}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="quick">
            <button className="quick-item" onClick={() => go("forecast")}>
              <strong>Cash forecast</strong>
              <span>{data.current_balance == null ? "Set your balance to see the next 90 days" : `Starting from ${money(data.current_balance, { cents: false })}`}</span>
            </button>
            <button className="quick-item" onClick={() => go("ask")}>
              <strong>Ask your books</strong>
              <span>"What did I spend on software last quarter?"</span>
            </button>
          </section>
        </>
      )}
    </div>
  );
}
