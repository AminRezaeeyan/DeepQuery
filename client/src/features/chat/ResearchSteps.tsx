import { useState } from "react";
import { BookOpen, Check, ChevronRight, FileSearch, FileText, Globe, Link2, ListChecks, LoaderCircle, SquareTerminal, TextSearch } from "lucide-react";
import type { AgentStep } from "../../lib/types";

const ICONS: Record<string, typeof Globe> = {
  search_documents: FileSearch,
  read_document: FileText,
  find_text: TextSearch,
  web_search: Globe,
  fetch_page: Link2,
  wikipedia: BookOpen,
  run_python: SquareTerminal,
  check_answer: ListChecks,
};

function StepList({ steps }: { steps: AgentStep[] }) {
  return (
    <ol className="steps-list">
      {steps.map((step, i) => {
        const Icon = ICONS[step.tool] ?? FileSearch;
        const running = step.status === "running";
        return (
          <li key={step.id ?? i} className={running ? "is-running" : ""}>
            <Icon size={13} className="step-icon" />
            <span className="step-text" dir="auto">
              {step.summary}
            </span>
            {running ? <LoaderCircle size={12} className="spin step-state" /> : <Check size={12} className="step-state" />}
          </li>
        );
      })}
    </ol>
  );
}

/** The agent's research trail: live while it works, folded into one line once the answer is in. */
export function ResearchSteps({ steps, live }: { steps: AgentStep[]; live: boolean }) {
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;

  if (live) {
    // One quiet line for what the agent is doing now; the answer is the only thing that streams.
    const current = steps[steps.length - 1];
    const Icon = ICONS[current.tool] ?? FileSearch;
    return (
      <div className="steps-live" aria-live="polite">
        <span className="thinking-bar" />
        <Icon size={13} className="step-icon" />
        <span className="step-text" dir="auto">
          {current.summary}
        </span>
        <span className="steps-count">step {steps.length}</span>
      </div>
    );
  }

  return (
    <div className="steps">
      <button className="steps-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <ChevronRight size={13} className={`steps-chevron ${open ? "is-open" : ""}`} />
        Researched in {steps.length} {steps.length === 1 ? "step" : "steps"}
      </button>
      {open && <StepList steps={steps} />}
    </div>
  );
}
