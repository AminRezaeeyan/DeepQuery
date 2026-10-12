import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { AuthLayout } from "./AuthLayout";
import { useAuth } from "../lib/auth";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

type GoogleId = {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
    };
  };
};

/** Google sign-in, shown only when VITE_GOOGLE_CLIENT_ID is set. */
function GoogleButton({ onError }: { onError: (msg: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { googleLogin } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !ref.current) return;
    const el = ref.current;
    const render = () => {
      const google = (window as unknown as { google?: GoogleId }).google;
      if (!google) return;
      google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: ({ credential }) =>
          googleLogin(credential)
            .then(() => navigate("/"))
            .catch((e: Error) => onError(e.message)),
      });
      google.accounts.id.renderButton(el, { theme: "outline", size: "large", width: el.offsetWidth, shape: "rectangular" });
    };
    const existing = document.querySelector<HTMLScriptElement>("script[data-gsi]");
    if (existing) return render();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.dataset.gsi = "1";
    s.onload = render;
    document.head.appendChild(s);
  }, [googleLogin, navigate, onError]);

  if (!GOOGLE_CLIENT_ID) return null;
  return (
    <>
      <div className="divider">
        <span>or</span>
      </div>
      <div ref={ref} className="google-btn" />
    </>
  );
}

function PasswordField({ value, onChange, autoComplete }: { value: string; onChange: (v: string) => void; autoComplete: string }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="input-affix">
      <input
        id="password"
        type={shown ? "text" : "password"}
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        minLength={8}
        required
      />
      <button type="button" className="icon-btn icon-btn--sm" onClick={() => setShown((s) => !s)} aria-label={shown ? "Hide password" : "Show password"}>
        {shown ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
}

function SubmitButton({ busy, label }: { busy: boolean; label: string }) {
  return (
    <button className="btn btn--primary btn--block" disabled={busy}>
      {busy ? <LoaderCircle size={16} className="spin" /> : null}
      {label}
      {!busy && <ArrowRight size={16} />}
    </button>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to pick up your research where you left it.">
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span>Email</span>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required autoFocus />
        </label>
        <label className="field">
          <span>Password</span>
          <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        </label>
        {error && <p className="form-error">{error}</p>}
        <SubmitButton busy={busy} label="Sign in" />
      </form>
      <GoogleButton onError={setError} />
      <p className="auth-switch">
        New to DeepQuery? <Link to="/register">Create an account</Link>
      </p>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register({ ...form, email: form.email.trim() });
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Create your account" subtitle="Free plan included. No card needed.">
      <form className="form" onSubmit={submit}>
        <div className="field-row">
          <label className="field">
            <span>First name</span>
            <input className="input" value={form.first_name} onChange={(e) => set("first_name")(e.target.value)} autoComplete="given-name" autoFocus />
          </label>
          <label className="field">
            <span>Last name</span>
            <input className="input" value={form.last_name} onChange={(e) => set("last_name")(e.target.value)} autoComplete="family-name" />
          </label>
        </div>
        <label className="field">
          <span>Email</span>
          <input className="input" type="email" value={form.email} onChange={(e) => set("email")(e.target.value)} autoComplete="email" required />
        </label>
        <label className="field">
          <span>
            Password <em className="field-hint">at least 8 characters</em>
          </span>
          <PasswordField value={form.password} onChange={set("password")} autoComplete="new-password" />
        </label>
        {error && <p className="form-error">{error}</p>}
        <SubmitButton busy={busy} label="Create account" />
      </form>
      <GoogleButton onError={setError} />
      <p className="auth-switch">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
