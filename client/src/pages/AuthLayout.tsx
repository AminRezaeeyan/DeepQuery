import type { ReactNode } from "react";
import { Logo } from "../components/Logo";
import { ThemeSwitch } from "../components/ThemeSwitch";

/** A sample of what an answer looks like, shown beside the sign-in form. */
function Specimen() {
  return (
    <div className="specimen" aria-hidden="true">
      <div className="specimen-q">
        <span className="mono-label">Query</span>
        <p>Do the two trial reports agree on the effect size?</p>
      </div>

      <div className="specimen-a">
        <p>
          Both reports find a positive effect, but they disagree on its size.
        </p>
        <p>
          <mark>
            Source <span className="cite cite--static">1</span> reports a 12% reduction, but Source
            <span className="cite cite--static">2</span> measures 7% over a longer window.
          </mark>
        </p>
      </div>

      <ol className="specimen-sources">
        <li>
          <span className="src-num">1</span>
          <span className="src-name">trial-report-2021.pdf</span>
          <span className="src-kind">PDF</span>
        </li>
        <li>
          <span className="src-num">2</span>
          <span className="src-name">journal.example.org</span>
          <span className="src-kind">Web</span>
        </li>
      </ol>
    </div>
  );
}

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="auth">
      <section className="auth-form-side">
        <header className="auth-top">
          <Logo size={24} />
          <ThemeSwitch />
        </header>

        <div className="auth-form-wrap">
          <h1 className="auth-title">{title}</h1>
          <p className="auth-sub">{subtitle}</p>
          {children}
        </div>

        <footer className="auth-foot">Documents, the web and your notes — with a source behind every claim.</footer>
      </section>

      <section className="auth-art">
        <div className="auth-art-inner">
          <p className="auth-art-kicker mono-label">Research, with receipts</p>
          <h2 className="auth-art-title">
            Answers you can check,
            <br />
            line by line.
          </h2>
          <Specimen />
        </div>
      </section>
    </div>
  );
}
