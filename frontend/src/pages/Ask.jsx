import { useState } from "react";
import { api, money, shortDate } from "../api.js";
import { Amount, ErrorNote } from "../components/ui.jsx";

const EXAMPLES = [
  "How much did I spend on software last quarter?",
  "What were my top 3 expense categories last month?",
  "How much income came in this year?",
  "How much have I spent at Starbucks since July?",
];

export default function Ask() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (q) => {
    const text = (q ?? question).trim();
    if (text.length < 3) return setError("Type a question first.");
    setBusy(true);
    setError("");
    try {
      const r = await api("/api/ask", { method: "POST", body: { question: text } });
      setHistory((h) => [{ question: text, ...r }, ...h]);
      setQuestion("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Ask your books</h1>
        <p className="lede">Answers come from your actual transactions, and you can see every one behind the number.</p>
      </header>

      <form
        className="ask-box"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about your spending or income" maxLength={300} aria-label="Your question" />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Checking…" : "Ask"}</button>
      </form>
      <ErrorNote error={error} />

      {history.length === 0 && (
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="example" onClick={() => submit(ex)} disabled={busy}>
              {ex}
            </button>
          ))}
        </div>
      )}

      <div aria-live="polite" className="sr-only">{busy ? "Checking your books" : history[0] ? `Answer: ${history[0].answer}` : ""}</div>
      {history.map((h, i) => (
        <article className="answer" key={history.length - i}>
          <p className="answer-q">{h.question}</p>
          <p className="answer-a">{h.answer}</p>
          {h.result?.groups?.length > 0 && (
            <ul className="bars compact">
              {h.result.groups.map((g) => (
                <li key={g.key}>
                  <span className="bar-label">{g.key}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${(g.total / h.result.groups.reduce((m, x) => Math.max(m, x.total), 1)) * 100}%` }} />
                  </span>
                  <span className="bar-value">{money(g.total, { cents: false })}</span>
                </li>
              ))}
            </ul>
          )}
          {h.result && (
            <details className="items">
              <summary>
                Show the {h.result.count} transaction{h.result.count === 1 ? "" : "s"} behind this
                {h.plan?.date_from && ` (${shortDate(h.plan.date_from)} to ${h.plan?.date_to ? shortDate(h.plan.date_to) : "today"})`}
              </summary>
              <ul>
                {h.result.transactions.map((t) => (
                  <li key={t.id}>
                    <span>
                      {shortDate(t.date)}, {t.merchant} <span className="muted">({t.category})</span>
                    </span>
                    <Amount value={t.amount} />
                  </li>
                ))}
                {h.result.count > h.result.transactions.length && <li className="muted">Showing the latest 100.</li>}
              </ul>
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
