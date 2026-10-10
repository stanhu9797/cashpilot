import { useState } from "react";
import { api } from "../api.js";
import { ErrorNote } from "../components/ui.jsx";

export default function Login({ onSignedIn }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const validate = () => {
    const e = {};
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) e.email = "Enter a valid email address.";
    if (form.password.length < 8) e.password = "Use at least 8 characters.";
    else if (new TextEncoder().encode(form.password).length > 72) e.password = "Use 72 characters or fewer.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev) => {
    ev.preventDefault();
    setError("");
    if (!validate()) return;
    setBusy(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body = mode === "login" ? { email: form.email, password: form.password } : form;
      const res = await api(path, { method: "POST", body });
      onSignedIn(res.token, res.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm({ ...form, [key]: e.target.value }),
    "aria-invalid": Boolean(errors[key]),
  });

  return (
    <div className="auth">
      <div className="auth-intro">
        <div className="brand brand-lg">
          <span className="brand-mark" aria-hidden="true" />
          CashPilot
        </div>
        <h1>Ten minutes a week on your books. That's the whole job.</h1>
        <p>Snap receipts, import your bank file, and see cash problems weeks before they happen. Anything the app isn't sure about gets highlighted for you to check.</p>
      </div>

      <form className="auth-card" onSubmit={submit} noValidate>
        <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
        {mode === "register" && (
          <label>
            Name
            <input type="text" autoComplete="name" maxLength={120} {...field("name")} />
          </label>
        )}
        <label>
          Email
          <input type="email" autoComplete="email" maxLength={255} aria-describedby={errors.email ? "err-email" : undefined} {...field("email")} />
          {errors.email && <span className="field-error" id="err-email">{errors.email}</span>}
        </label>
        <label>
          Password
          <input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} maxLength={72} aria-describedby={errors.password ? "err-password" : undefined} {...field("password")} />
          {errors.password && <span className="field-error" id="err-password">{errors.password}</span>}
        </label>
        <ErrorNote error={error} />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "One moment…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <p className="auth-switch">
          {mode === "login" ? "New here? " : "Already have an account? "}
          <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setErrors({}); }}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
        <p className="hint">Trying it out? Run <code>python -m app.seed</code> and sign in as demo@cashpilot.app / demo-password.</p>
      </form>
    </div>
  );
}
