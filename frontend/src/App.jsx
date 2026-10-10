import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import Layout from "./components/Layout.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import Login from "./pages/Login.jsx";
import Overview from "./pages/Overview.jsx";
import Transactions from "./pages/Transactions.jsx";
import AddReceipt from "./pages/AddReceipt.jsx";
import Ask from "./pages/Ask.jsx";
import Forecast from "./pages/Forecast.jsx";

const PAGES = { overview: Overview, transactions: Transactions, receipt: AddReceipt, ask: Ask, forecast: Forecast };
const pageFromHash = () => {
  const p = window.location.hash.replace("#/", "").split("?")[0];
  return PAGES[p] ? p : "overview";
};

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(getToken()));
  const [page, setPage] = useState(pageFromHash());

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    const onSignedOut = () => setUser(null);
    window.addEventListener("hashchange", onHash);
    window.addEventListener("cashpilot:signed-out", onSignedOut);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("cashpilot:signed-out", onSignedOut);
    };
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    api("/api/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setChecking(false));
  }, []);

  const go = useCallback((p) => {
    window.location.hash = `#/${p}`;
    window.scrollTo(0, 0);
  }, []);

  const signOut = () => {
    setToken(null);
    setUser(null);
  };

  if (checking) return <div className="boot">Loading your books…</div>;
  if (!user)
    return (
      <Login
        onSignedIn={(token, u) => {
          setToken(token);
          setUser(u);
          go("overview");
        }}
      />
    );

  const Page = PAGES[page];
  return (
    <Layout page={page} go={go} user={user} onSignOut={signOut}>
      <ErrorBoundary resetKey={page}>
        <Page go={go} user={user} setUser={setUser} />
      </ErrorBoundary>
    </Layout>
  );
}
