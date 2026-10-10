import { useEffect, useRef, useState } from "react";
import { api, parseAmount, shortDate, todayISO } from "../api.js";
import { Amount, CategorySelect, Confidence, ErrorNote, Spinner } from "../components/ui.jsx";

const emptyForm = { date: todayISO(), merchant: "", amount: "", kind: "out", category: "" };

export default function Transactions() {
  const [txns, setTxns] = useState(null);
  const [categories, setCategories] = useState([]);
  const [reviewOnly, setReviewOnly] = useState(window.location.hash.includes("review"));
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [importing, setImporting] = useState(false);
  const [recat, setRecat] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  const load = () => {
    setError("");
    const params = new URLSearchParams();
    if (reviewOnly) params.set("needs_review", "true");
    if (search.trim()) params.set("search", search.trim());
    api(`/api/transactions?${params}`).then(setTxns).catch((e) => setError(e.message));
  };

  useEffect(() => {
    api("/api/categories").then(setCategories).catch(() => {});
  }, []);
  useEffect(() => {
    const t = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(t);
  }, [reviewOnly, search]);

  const replace = (updated) => {
    setTxns((list) => (reviewOnly && !updated.needs_review ? list.filter((t) => t.id !== updated.id) : list.map((t) => (t.id === updated.id ? updated : t))));
  };

  const changeCategory = async (t, category) => {
    setBusyId(t.id);
    try {
      replace(await api(`/api/transactions/${t.id}/category`, { method: "PATCH", body: { category, remember: true } }));
      setNotice(`Saved. Future charges from "${t.merchant}" will go to ${category}.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (t) => {
    if (!window.confirm(`Delete ${t.merchant} (${t.amount})? This can't be undone.`)) return;
    setBusyId(t.id);
    try {
      await api(`/api/transactions/${t.id}`, { method: "DELETE" });
      setTxns((list) => list.filter((x) => x.id !== t.id));
      setNotice("Transaction deleted.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const confirm = async (t) => {
    setBusyId(t.id);
    try {
      replace(await api(`/api/transactions/${t.id}/confirm`, { method: "POST" }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const onImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file exported from your bank.");
      return;
    }
    setImporting(true);
    setError("");
    setNotice("");
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api("/api/transactions/import", { method: "POST", form });
      setNotice(
        `Imported ${r.imported} transaction${r.imported === 1 ? "" : "s"}` +
          (r.skipped_duplicates ? `, skipped ${r.skipped_duplicates} already in your books` : "") +
          `. ${r.needs_review} need a quick check.` +
          (r.ai_available ? "" : " Add an AI key to auto-categorize unfamiliar merchants.")
      );
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setImporting(false);
    }
  };

  const recategorize = async () => {
    setRecat(true);
    setError("");
    try {
      const r = await api("/api/transactions/recategorize", { method: "POST" });
      setNotice(`Re-checked ${r.updated}. ${r.still_needs_review} still need you.`);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setRecat(false);
    }
  };

  const validateForm = () => {
    const e = {};
    if (!form.merchant.trim()) e.merchant = "Enter who you paid or who paid you.";
    const n = parseAmount(form.amount);
    if (Number.isNaN(n) || n <= 0) e.amount = "Enter an amount greater than 0, like 42.50.";
    else if (n > 10000000) e.amount = "That amount looks too large. Check for a typo.";
    if (!form.date) e.date = "Pick a date.";
    else if (form.date > todayISO()) e.date = "Date can't be in the future.";
    setFormErrors(e);
    return Object.keys(e).length === 0;
  };

  const addTxn = async (ev) => {
    ev.preventDefault();
    if (!validateForm()) return;
    setSaving(true);
    try {
      const amount = parseAmount(form.amount) * (form.kind === "out" ? -1 : 1);
      const created = await api("/api/transactions", {
        method: "POST",
        body: { date: form.date, merchant: form.merchant.trim(), amount, category: form.category || null },
      });
      setTxns((l) => [created, ...(l || [])]);
      setForm(emptyForm);
      setShowAdd(false);
      setNotice("Transaction added.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head with-actions">
        <h1>Transactions</h1>
        <div className="row">
          <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={onImport} />
          <button className="btn" onClick={() => fileRef.current?.click()} disabled={importing}>
            {importing ? "Importing…" : "Import bank CSV"}
          </button>
          <button className="btn btn-primary" onClick={() => setShowAdd((s) => !s)}>
            {showAdd ? "Close" : "Add transaction"}
          </button>
        </div>
      </header>

      {showAdd && (
        <form className="panel add-form" onSubmit={addTxn} noValidate>
          <div className="seg" role="radiogroup" aria-label="Type">
            {["out", "in"].map((k) => (
              <button type="button" key={k} role="radio" aria-checked={form.kind === k} className={form.kind === k ? "on" : ""} onClick={() => setForm({ ...form, kind: k })}>
                {k === "out" ? "Money out" : "Money in"}
              </button>
            ))}
          </div>
          <label>
            Merchant or client
            <input value={form.merchant} onChange={(e) => setForm({ ...form, merchant: e.target.value })} aria-invalid={Boolean(formErrors.merchant)} aria-describedby={formErrors.merchant ? "err-merchant" : undefined} maxLength={255} />
            {formErrors.merchant && <span className="field-error" id="err-merchant">{formErrors.merchant}</span>}
          </label>
          <label>
            Amount
            <input inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} aria-invalid={Boolean(formErrors.amount)} aria-describedby={formErrors.amount ? "err-amount" : undefined} placeholder="0.00" />
            {formErrors.amount && <span className="field-error" id="err-amount">{formErrors.amount}</span>}
          </label>
          <label>
            Date
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} aria-invalid={Boolean(formErrors.date)} aria-describedby={formErrors.date ? "err-date" : undefined} />
            {formErrors.date && <span className="field-error" id="err-date">{formErrors.date}</span>}
          </label>
          <label>
            Category
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              <option value="">Suggest one for me</option>
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save transaction"}</button>
        </form>
      )}

      <div className="toolbar">
        <input type="search" className="search" placeholder="Search merchants" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search merchants" />
        <label className="toggle">
          <input type="checkbox" checked={reviewOnly} onChange={(e) => setReviewOnly(e.target.checked)} />
          Only show items to check
        </label>
        {reviewOnly && txns?.length > 0 && (
          <button className="link" onClick={recategorize} disabled={recat}>
            {recat ? "Re-checking…" : "Re-run suggestions"}
          </button>
        )}
      </div>

      {notice && <div className="ok-note" role="status">{notice}</div>}
      <ErrorNote error={error} onRetry={load} />

      {!txns ? (
        <Spinner label="Loading transactions" />
      ) : txns.length === 0 ? (
        <div className="empty">
          <h2>{reviewOnly ? "Nothing left to check" : search ? "No matches" : "No transactions yet"}</h2>
          <p>{reviewOnly ? "Every transaction is confirmed." : search ? "Try a different merchant name." : "Import a CSV from your bank to get started."}</p>
        </div>
      ) : (
        <ul className="txn-list">
          {txns.map((t) => (
            <li key={t.id} className={`txn ${t.needs_review ? "txn-review" : ""}`}>
              <div className="txn-main">
                <span className="txn-date">{shortDate(t.date)}</span>
                <span className="txn-merchant">{t.merchant}</span>
                <Amount value={t.amount} />
              </div>
              <div className="txn-meta">
                <label htmlFor={`cat-${t.id}`} className="sr-only">Category for {t.merchant}</label>
                <CategorySelect id={`cat-${t.id}`} value={t.category} categories={categories} disabled={busyId === t.id} onChange={(c) => changeCategory(t, c)} />
                <Confidence txn={t} />
                {t.needs_review && (
                  <button className="btn btn-small" onClick={() => confirm(t)} disabled={busyId === t.id}>
                    Looks right
                  </button>
                )}
                <button className="link link-danger" onClick={() => remove(t)} disabled={busyId === t.id} aria-label={`Delete ${t.merchant}`}>
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
