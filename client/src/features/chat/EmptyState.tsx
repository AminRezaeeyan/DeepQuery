import { FileSearch, GitCompareArrows, Globe, ShieldQuestion } from "lucide-react";

const STARTERS = [
  {
    icon: GitCompareArrows,
    kind: "Compare",
    text: "Where do my uploaded documents disagree with each other?",
  },
  {
    icon: Globe,
    kind: "Verify",
    text: "Check this claim against recent sources on the web: ",
  },
  {
    icon: FileSearch,
    kind: "Extract",
    text: "Pull out the key numbers in these files and cite where each one comes from.",
  },
  {
    icon: ShieldQuestion,
    kind: "Challenge",
    text: "What is the weakest part of the argument in this document?",
  },
];

export function EmptyState({ name, onPick }: { name: string; onPick: (text: string) => void }) {
  const hour = new Date().getHours();
  const greet = hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="empty">
      <p className="empty-kicker mono-label">
        <span className="caret">&gt;</span> {greet}
        {name ? `, ${name}` : ""}
      </p>
      <h2 className="empty-title">What are we looking into?</h2>
      <p className="empty-sub">Add files, turn on web search, or just ask. Every claim in the answer links back to where it came from.</p>
      <div className="starters">
        {STARTERS.map(({ icon: Icon, kind, text }) => (
          <button key={kind} className="starter" onClick={() => onPick(text)}>
            <span className="starter-kind">
              <Icon size={14} />
              {kind}
            </span>
            <span className="starter-text">{text.trim()}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
