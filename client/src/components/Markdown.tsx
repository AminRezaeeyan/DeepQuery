import { memo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";
import { linkCitations, type Reference } from "../lib/format";

function CodeBlock({ children, ...rest }: React.HTMLAttributes<HTMLPreElement>) {
  const [copied, setCopied] = useState(false);
  const child = Array.isArray(children) ? children[0] : children;
  const className: string = (child as { props?: { className?: string } })?.props?.className ?? "";
  const lang = className.match(/language-(\w+)/)?.[1];

  const copy = (e: React.MouseEvent<HTMLButtonElement>) => {
    const text = e.currentTarget.closest(".code")?.querySelector("pre")?.innerText ?? "";
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    });
  };

  return (
    <div className="code">
      <div className="code-bar">
        <span>{lang ?? "text"}</span>
        <button onClick={copy} className="code-copy">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre {...rest}>{children}</pre>
    </div>
  );
}

type Props = { text: string; references?: Reference[]; onCite?: (id: number) => void };

export const Markdown = memo(function Markdown({ text, references = [], onCite }: Props) {
  const components: Components = {
    pre: CodeBlock,
    a: ({ href, children }) => {
      const cite = href?.match(/^#cite-(\d+)$/);
      if (cite) {
        const id = Number(cite[1]);
        const ref = references.find((r) => r.id === id);
        return (
          <button
            type="button"
            className="cite"
            data-tip={ref?.label ?? `Source ${id}`}
            onClick={() => onCite?.(id)}
            aria-label={`Source ${id}${ref ? `: ${ref.label}` : ""}`}
          >
            {id}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      );
    },
    table: ({ children }) => (
      <div className="table-wrap">
        <table>{children}</table>
      </div>
    ),
  };

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeHighlight, { detect: false }]]} components={components}>
      {linkCitations(text)}
    </ReactMarkdown>
  );
});
