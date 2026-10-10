// Small fetch wrapper: adds the sign-in token, turns server errors into readable messages.
const TOKEN_KEY = "cashpilot_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Empty when the backend serves the frontend (local dev, Docker). Set VITE_API_BASE at build time when
// the frontend is hosted separately, e.g. on AWS Amplify with the API on AWS Lambda.
const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(API_BASE + path, { method, headers, body: payload });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running.", 0);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    if (res.status === 401) {
      setToken(null);
      window.dispatchEvent(new Event("cashpilot:signed-out"));
    }
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${res.status}).`;
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const money = (n, { sign = false, cents = true } = {}) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const s = Math.abs(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  });
  if (v < 0) return `−${s}`;
  return sign && v > 0 ? `+${s}` : s;
};

export const shortDate = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });

// Local calendar date as YYYY-MM-DD (toISOString would use UTC and can be "tomorrow" in the evening)
export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Accepts what people actually type: "1,200", "$12.50", " 45 ", "(30.00)". Returns NaN if it isn't a number.
export const parseAmount = (raw) => {
  let v = String(raw ?? "").trim().replace(/[$,\s]/g, "");
  if (/^\(.*\)$/.test(v)) v = "-" + v.slice(1, -1);
  if (!/^-?\d*\.?\d+$/.test(v)) return NaN;
  return Number(v);
};
