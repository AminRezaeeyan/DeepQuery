import { useState } from "react";
import { FileUp, LoaderCircle, Trash2, TriangleAlert, X } from "lucide-react";
import { extOf } from "../../lib/format";
import type { UIDoc } from "./useDocuments";

const STATUS: Record<string, string> = {
  pending: "Queued",
  processing: "Indexing",
  done: "Ready",
  failed: "Failed",
};

function DocRow({ doc, onRemove }: { doc: UIDoc; onRemove: () => void }) {
  const ext = extOf(doc.original_filename);
  const busy = doc.uploading || doc.status === "pending" || doc.status === "processing";
  return (
    <li className={`doc doc--${doc.status}`}>
      <span className="doc-ext">{ext || "doc"}</span>
      <span className="doc-text">
        <span className="doc-name" title={doc.original_filename ?? ""}>
          {doc.original_filename ?? "Web page"}
        </span>
        <span className="doc-status">
          {busy && <LoaderCircle size={11} className="spin" />}
          {doc.status === "failed" && <TriangleAlert size={11} />}
          {doc.uploading ? "Uploading" : STATUS[doc.status]}
        </span>
      </span>
      {!doc.uploading && (
        <button className="icon-btn icon-btn--sm doc-remove" onClick={onRemove} aria-label={`Remove ${doc.original_filename}`}>
          <Trash2 size={14} />
        </button>
      )}
    </li>
  );
}

type Props = {
  docs: UIDoc[];
  onUpload: (files: File[]) => void;
  onRemove: (uuid: string) => void;
  onClose: () => void;
  accept: string;
};

export function SourcesPanel({ docs, onUpload, onRemove, onClose, accept }: Props) {
  const [over, setOver] = useState(false);

  return (
    <aside className="sources-panel" aria-label="Sources for this chat">
      <header className="panel-head">
        <div>
          <h2>Sources</h2>
          <p>Answers in this chat draw on these files.</p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close sources">
          <X size={18} />
        </button>
      </header>

      <label
        className={`dropzone ${over ? "is-over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          onUpload(Array.from(e.dataTransfer.files));
        }}
      >
        <FileUp size={20} />
        <span>
          <strong>Add files</strong> or drop them here
        </span>
        <small>PDF, TXT, MD, CSV, XLSX, JSON and code files</small>
        <input
          type="file"
          multiple
          hidden
          accept={accept}
          onChange={(e) => {
            onUpload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </label>

      {docs.length > 0 ? (
        <ul className="doc-list">
          {docs.map((d) => (
            <DocRow key={d.uuid} doc={d} onRemove={() => onRemove(d.uuid)} />
          ))}
        </ul>
      ) : (
        <p className="panel-empty">
          No files yet. Without files, answers rely on web search (when it’s on) and what you’ve told DeepQuery before.
        </p>
      )}
    </aside>
  );
}
