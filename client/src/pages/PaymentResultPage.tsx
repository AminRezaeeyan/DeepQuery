import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, CircleCheck, CircleX, LoaderCircle } from "lucide-react";
import { api } from "../lib/api";
import { Logo } from "../components/Logo";
import { ThemeSwitch } from "../components/ThemeSwitch";

type Result =
  | { state: "verifying" }
  | { state: "success"; plan: string; refId: string }
  | { state: "failed"; message: string };

const planName = (name: string) => name.charAt(0) + name.slice(1).toLowerCase();

/** Where ZarinPal sends the user back after paying (or cancelling). */
export function PaymentResultPage() {
  const [params] = useSearchParams();
  const [result, setResult] = useState<Result>({ state: "verifying" });
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // verify once, even when effects run twice in development
    started.current = true;

    const authority = params.get("Authority");
    const status = params.get("Status");
    if (!authority || !status) {
      setResult({ state: "failed", message: "This link doesn’t contain a payment to confirm." });
      return;
    }
    api.verifyPayment(authority, status).then(
      (r) => setResult({ state: "success", plan: r.plan, refId: r.ref_id }),
      (e: Error) => setResult({ state: "failed", message: e.message }),
    );
  }, [params]);

  return (
    <div className="plans-page">
      <header className="plans-top">
        <span />
        <Logo size={20} />
        <ThemeSwitch />
      </header>

      <section className="payment-result" aria-live="polite">
        {result.state === "verifying" && (
          <>
            <LoaderCircle size={34} className="spin payment-icon" />
            <h1>Confirming your payment…</h1>
            <p>This takes a few seconds. Please keep this page open.</p>
          </>
        )}

        {result.state === "success" && (
          <>
            <CircleCheck size={40} className="payment-icon payment-icon--ok" />
            <h1>You’re on the {planName(result.plan)} plan</h1>
            <p>Your payment went through and your new limits apply now, for the next 30 days.</p>
            <dl className="payment-ref">
              <dt>Reference number</dt>
              <dd>{result.refId}</dd>
            </dl>
            <Link to="/" className="btn btn--primary">
              Back to research <ArrowRight size={16} />
            </Link>
          </>
        )}

        {result.state === "failed" && (
          <>
            <CircleX size={40} className="payment-icon payment-icon--fail" />
            <h1>Payment not completed</h1>
            <p>{result.message} No upgrade was applied.</p>
            <div className="payment-actions">
              <Link to="/plans" className="btn btn--primary">
                Back to plans
              </Link>
              <Link to="/" className="btn btn--ghost">
                Back to research
              </Link>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
