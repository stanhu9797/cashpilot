import { useEffect, useRef, useState } from "react";
import { api, money, parseAmount, todayISO } from "../api.js";
import { ErrorNote } from "../components/ui.jsx";

const MAX_MB = 10;
const TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

export default function AddReceipt({ go }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [stage, setStage] = useState("pick"); // pick | reading | review | saved
  const [result, setResult] = useState(null);
  const [form, setForm] = useState(null);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    api("/api/categories").then(setCategories).catch(() => {});
  }, []);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const choose = (f) => {
    setError("");
    if (!f) return;
    if (!TYPES.includes(f.type)) return setError("Choose a photo (JPG, PNG, WEBP) or a PDF.");
    if (f.size > MAX_MB * 1024 * 1024) return setError(`That file is over ${MAX_MB} MB. Try a smaller photo.`);
    setFile(f);
    setPreview(f.type.startsWith("image/") ? URL.createObjectURL(f) : null);
    read(f);
  };

  const read = async (f) => {
    setStage("reading");
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await api("/api/receipts", { method: "POST", form: fd });
      setResult(r);
      const x = r.extracted;
      setForm({
        merchant: x.merchant || "",
        date: x.date || todayISO(),
        total: x.total != null ? String(x.total) : "",
        category: r.category_suggestion?.category || "Other",
      });
      setStage("review");
    } catch (e) {
      setError(e.message);
      setStage("pick");
    }
  };

  const low = (field) => {
    if (!result) return false;
    return (result.extracted.confidence?.[field] ?? 0) < result.review_threshold;
  };

  const save = async (ev) => {
    ev.preventDefault();
    setError("");
    const total = parseAmount(form.total);
    if (!form.merchant.trim()) return setError("Add the merchant name.");
    if (Number.isNaN(total) || total <= 0) return setError("Add the total as a number greater than 0, like 18.40.");
    if (!form.date || form.date > todayISO()) return setError("Check the date. It can't be in the future.");
    setSaving(true);
    try {
      await api("/api/transactions", {
        method: "POST",
        body: { date: form.date, merchant: form.merchant.trim(), amount: -Math.abs(total), category: form.category, receipt_id: result.receipt_id },
      });
      setStage("saved");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setForm(null);
    setError("");
    setStage("pick");
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Add a receipt</h1>
      </header>

      {stage === "pick" && (
        <>
          <div
            className="dropzone"
            role="group"
            aria-label="Receipt upload"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              choose(e.dataTransfer.files?.[0]);
            }}
          >
            <p className="dz-title">Take a photo or choose a file</p>
            <p className="muted">Flat, well-lit, and the whole receipt in frame works best. JPG, PNG, WEBP, or PDF up to {MAX_MB} MB.</p>
            <input ref={inputRef} type="file" accept="image/*,application/pdf" capture="environment" hidden onChange={(e) => choose(e.target.files?.[0])} />
            <button className="btn btn-primary" onClick={() => inputRef.current?.click()}>
              Choose receipt
            </button>
          </div>
          <ErrorNote error={error} />
        </>
      )}

      {stage === "reading" && (
        <div className="reading">
          {preview && <img src={preview} alt="Your receipt" className="receipt-img" />}
          <div className="reading-text" role="status">
            <span className="spinner-dot" aria-hidden="true" />
            Reading {file?.name || "your receipt"}…
          </div>
        </div>
      )}

      {stage === "review" && form && (
        <div className="review-grid">
          {preview ? <img src={preview} alt="Your receipt" className="receipt-img" /> : <div className="pdf-chip">{file?.name}</div>}

          <form className="panel" onSubmit={save} noValidate>
            <h2>Check what we read</h2>
            <p className="muted small">
              <span className="hl">Highlighted fields</span> are ones the AI wasn't sure about. Fix anything that's off, then save.
            </p>

            <label className={low("merchant") ? "field-low" : ""}>
              Merchant
              <input value={form.merchant} maxLength={255} onChange={(e) => setForm({ ...form, merchant: e.target.value })} />
            </label>
            <label className={low("total") ? "field-low" : ""}>
              Total paid
              <input inputMode="decimal" value={form.total} onChange={(e) => setForm({ ...form, total: e.target.value })} />
            </label>
            <label className={low("date") ? "field-low" : ""}>
              Date
              <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </label>
            <label className={result.category_suggestion && result.category_suggestion.confidence < result.review_threshold ? "field-low" : ""}>
              Category
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>

            {result.extracted.warnings?.length > 0 && (
              <ul className="warn-list">
                {result.extracted.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            {result.extracted.notes && <p className="muted small">AI note: {result.extracted.notes}</p>}

            {result.extracted.line_items?.length > 0 && (
              <details className="items">
                <summary>{result.extracted.line_items.length} line items</summary>
                <ul>
                  {result.extracted.line_items.map((li, i) => (
                    <li key={i}>
                      <span>{li.description}</span>
                      <span>{li.amount != null ? money(li.amount) : ""}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            <ErrorNote error={error} />
            <div className="row">
              <button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save to my books"}</button>
              <button type="button" className="btn" onClick={reset}>Start over</button>
            </div>
          </form>
        </div>
      )}

      {stage === "saved" && (
        <div className="empty">
          <h2>Saved to your books</h2>
          <p>{form.merchant}, {money(-Math.abs(parseAmount(form.total)))}, filed under {form.category}.</p>
          <div className="row">
            <button className="btn btn-primary" onClick={reset}>Add another</button>
            <button className="btn" onClick={() => go("transactions")}>See transactions</button>
          </div>
        </div>
      )}
    </div>
  );
}
