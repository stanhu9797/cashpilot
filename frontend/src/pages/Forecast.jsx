import { useEffect, useState } from "react";
import { api, money, parseAmount, shortDate } from "../api.js";
import LineChart from "../components/LineChart.jsx";
import { Amount, ErrorNote, Spinner } from "../components/ui.jsx";

export default function Forecast({ user, setUser }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [needsBalance, setNeedsBalance] = useState(user.current_balance == null);
  const [settings, setSettings] = useState({
    balance: user.current_balance ?? "",
    threshold: user.low_balance_threshold ?? 1000,
  });
  const [saving, setSaving] = useState(false);
  const [explain, setExplain] = useState({ text: "", busy: false, error: "" });

  const load = () => {
    setError("");
    api("/api/forecast")
      .then((d) => {
        setData(d);
        setNeedsBalance(false);
      })
      .catch((e) => (e.status === 400 ? setNeedsBalance(true) : setError(e.message)));
  };
  useEffect(load, []);

  const saveSettings = async (ev) => {
    ev.preventDefault();
    const b = parseAmount(settings.balance);
    const t = parseAmount(settings.threshold);
    if (Number.isNaN(b)) return setError("Enter your current bank balance as a number, like 6,200.");
    if (Number.isNaN(t) || t < 0) return setError("Enter a low-balance line of 0 or more.");
    setSaving(true);
    setError("");
    try {
      const u = await api("/api/auth/settings", { method: "PUT", body: { current_balance: b, low_balance_threshold: t } });
      setUser(u);
      setExplain({ text: "", busy: false, error: "" });
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const getExplanation = async () => {
    setExplain({ text: "", busy: true, error: "" });
    try {
      const r = await api("/api/forecast/explain", { method: "POST" });
      setExplain({ text: r.explanation, busy: false, error: "" });
    } catch (e) {
      setExplain({ text: "", busy: false, error: e.message });
    }
  };

  const settingsForm = (
    <form className="panel settings-form" onSubmit={saveSettings} noValidate>
      <label>
        Current bank balance
        <input inputMode="decimal" value={settings.balance} onChange={(e) => setSettings({ ...settings, balance: e.target.value })} placeholder="e.g. 6200" />
      </label>
      <label>
        Warn me below
        <input inputMode="decimal" value={settings.threshold} onChange={(e) => setSettings({ ...settings, threshold: e.target.value })} />
      </label>
      <button className="btn btn-primary" disabled={saving}>{saving ? "Updating…" : "Update forecast"}</button>
    </form>
  );

  return (
    <div className="page">
      <header className="page-head">
        <h1>Next 90 days</h1>
        <p className="lede">Built from your regular bills and income, plus your typical everyday spending.</p>
      </header>

      <ErrorNote error={error} onRetry={needsBalance ? null : load} />

      {needsBalance ? (
        <>
          <p>Enter today's balance from your bank app so the forecast has a starting point.</p>
          {settingsForm}
        </>
      ) : !data ? (
        <Spinner label="Running the numbers" />
      ) : (
        <>
          {data.warnings.length > 0 ? (
            <div className="forecast-warnings">
              {data.warnings.map((w) => (
                <p key={w} className={w.includes("drop below") ? "hl-strong" : ""}>{w}</p>
              ))}
            </div>
          ) : (
            <div className="all-clear">Your balance stays above {money(data.low_threshold, { cents: false })} for the next 90 days.</div>
          )}

          <section className="panel">
            <div className="forecast-figures">
              <div>
                <span className="lt-label">Today</span>
                <span className="lt-value">{money(data.starting_balance, { cents: false })}</span>
              </div>
              <div>
                <span className="lt-label">Lowest point, {shortDate(data.lowest.date)}</span>
                <span className={`lt-value ${data.lowest.balance < data.low_threshold ? "out" : ""}`}>{money(data.lowest.balance, { cents: false })}</span>
              </div>
              <div>
                <span className="lt-label">In 90 days</span>
                <span className="lt-value">{money(data.ending_balance, { cents: false })}</span>
              </div>
            </div>
            <LineChart series={data.series} threshold={data.low_threshold} />
            <div className="explain">
              {explain.text ? (
                <p className="explain-text">{explain.text}</p>
              ) : (
                <button className="link" onClick={getExplanation} disabled={explain.busy}>
                  {explain.busy ? "Writing a summary…" : "Explain this in plain English"}
                </button>
              )}
              {explain.error && <p className="field-error">{explain.error}</p>}
            </div>
          </section>

          <div className="two-col">
            <section className="panel">
              <h2>Coming up in 30 days</h2>
              {data.upcoming_30_days.length === 0 ? (
                <p className="muted">No regular bills or income detected yet.</p>
              ) : (
                <ul className="simple-list">
                  {data.upcoming_30_days.map((u, i) => (
                    <li key={i}>
                      <span>{shortDate(u.date)}, {u.merchant}</span>
                      <Amount value={u.amount} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="panel">
              <h2>How this is calculated</h2>
              <p className="small">{data.method}</p>
              <p className="small">
                Everyday spending averages {money(data.daily_everyday_spending)}/day and other income {money(data.daily_everyday_income)}/day.
                {data.recurring.length > 0 && ` ${data.recurring.length} regular items found.`}
              </p>
              <details className="items">
                <summary>Change balance or warning line</summary>
                {settingsForm}
              </details>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
