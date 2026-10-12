import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, LoaderCircle } from "lucide-react";
import { api } from "../lib/api";
import type { Plan, Subscription } from "../lib/types";
import { Logo } from "../components/Logo";
import { ThemeSwitch } from "../components/ThemeSwitch";
import { useToast } from "../components/Toast";

const rials = new Intl.NumberFormat("en-US");

function PlanCard({ plan, current, featured, busy, onChoose }: { plan: Plan; current: boolean; featured: boolean; busy: boolean; onChoose: () => void }) {
  const free = plan.price === 0;
  return (
    <article className={`plan ${featured ? "plan--featured" : ""} ${current ? "is-current" : ""}`}>
      <header>
        <h2>{plan.name.charAt(0) + plan.name.slice(1).toLowerCase()}</h2>
        {current && <span className="tag">Current</span>}
      </header>
      <p className="plan-price">
        {free ? (
          <strong>Free</strong>
        ) : (
          <>
            <strong>{rials.format(plan.price)}</strong>
            <span>Rials / 30 days</span>
          </>
        )}
      </p>
      <ul className="plan-limits">
        <li>
          <Check size={15} />
          <span>
            <strong>{plan.daily_message_limit}</strong> messages a day
          </span>
        </li>
        <li>
          <Check size={15} />
          <span>
            <strong>{plan.daily_document_limit}</strong> document uploads a day
          </span>
        </li>
        <li>
          <Check size={15} />
          <span>
            <strong>{plan.daily_image_limit}</strong> image questions a day
          </span>
        </li>
      </ul>
      <button className={`btn btn--block ${featured && !current ? "btn--primary" : "btn--ghost"}`} disabled={current || free || busy} onClick={onChoose}>
        {busy && <LoaderCircle size={16} className="spin" />}
        {current ? "Your plan" : free ? "Included" : `Upgrade to ${plan.name.charAt(0) + plan.name.slice(1).toLowerCase()}`}
      </button>
    </article>
  );
}

export function PlansPage() {
  const toast = useToast();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [paying, setPaying] = useState<number | null>(null);

  useEffect(() => {
    api.plans().then(setPlans, (e: Error) => toast(e.message));
    api.subscription().then(setSub, () => undefined);
  }, [toast]);

  const choose = async (plan: Plan) => {
    setPaying(plan.id);
    try {
      const { payment_url } = await api.startPayment(plan.id);
      window.location.assign(payment_url);
    } catch (e) {
      toast((e as Error).message);
      setPaying(null);
    }
  };

  const sorted = plans ? [...plans].sort((a, b) => a.price - b.price) : null;
  const top = sorted?.[sorted.length - 1]?.id;

  return (
    <div className="plans-page">
      <header className="plans-top">
        <Link to="/" className="btn btn--ghost btn--sm">
          <ArrowLeft size={15} /> Back to research
        </Link>
        <Logo size={20} />
        <ThemeSwitch />
      </header>

      <section className="plans-hero">
        <p className="mono-label">Plans</p>
        <h1>More questions, more sources.</h1>
        <p>Limits reset every day. Payments go through ZarinPal; a paid plan runs for 30 days.</p>
        {sub?.end_date && (
          <p className="plans-renew">
            Your {sub.plan.name.toLowerCase()} plan runs until {new Date(sub.end_date).toLocaleDateString()}.
          </p>
        )}
      </section>

      <section className="plans-grid">
        {sorted
          ? sorted.map((p) => (
              <PlanCard
                key={p.id}
                plan={p}
                current={sub?.plan.id === p.id}
                featured={p.id === top && sorted.length > 1}
                busy={paying === p.id}
                onChoose={() => choose(p)}
              />
            ))
          : [0, 1].map((i) => <div key={i} className="plan skeleton skeleton--card" />)}
      </section>
    </div>
  );
}
