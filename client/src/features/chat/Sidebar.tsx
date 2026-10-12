import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { EyeOff, Gauge, LogOut, MoreHorizontal, PanelLeftClose, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { Logo } from "../../components/Logo";
import { ThemeSwitch } from "../../components/ThemeSwitch";
import { useAuth } from "../../lib/auth";
import { displayTitle, groupChats } from "../../lib/format";
import { useDismiss } from "../../lib/hooks";
import type { Chat, Subscription } from "../../lib/types";

type Props = {
  chats: Chat[];
  activeId: string | undefined;
  hasMore: boolean;
  onLoadMore: () => void;
  query: string;
  setQuery: (q: string) => void;
  searching: boolean;
  onNew: () => void;
  onRename: (uuid: string, title: string) => void;
  onDelete: (uuid: string) => void;
  onClose: () => void;
  subscription: Subscription | null;
  searchRef: React.RefObject<HTMLInputElement | null>;
};

function ChatRow({ chat, onRename, onDelete, onNavigate }: { chat: Chat; onRename: Props["onRename"]; onDelete: Props["onDelete"]; onNavigate: () => void }) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [title, setTitle] = useState(chat.title);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, menu, () => {
    setMenu(false);
    setConfirm(false);
  });

  if (renaming) {
    const done = (save: boolean) => {
      const t = title.trim();
      if (save && t && t !== chat.title) onRename(chat.uuid, t);
      setRenaming(false);
    };
    return (
      <div className="chat-row is-editing">
        <input
          className="chat-rename"
          value={title}
          autoFocus
          dir="auto"
          onFocus={(e) => e.target.select()}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => done(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter") done(true);
            if (e.key === "Escape") done(false);
          }}
        />
      </div>
    );
  }

  return (
    <div className={`chat-row ${menu ? "has-menu" : ""}`} ref={ref}>
      <NavLink to={`/c/${chat.uuid}`} className={({ isActive }) => `chat-link ${isActive ? "is-active" : ""}`} onClick={onNavigate}>
        {chat.is_temporary && <EyeOff size={13} className="chat-temp" aria-label="Temporary" />}
        <span dir="auto">{displayTitle(chat.title)}</span>
      </NavLink>
      <button className="chat-more" onClick={() => setMenu((m) => !m)} aria-label="Chat actions" aria-expanded={menu}>
        <MoreHorizontal size={15} />
      </button>
      {menu && (
        <div className="popover menu">
          {confirm ? (
            <>
              <p className="menu-note">Delete this chat and its sources?</p>
              <button className="menu-item is-danger" onClick={() => onDelete(chat.uuid)}>
                <Trash2 size={14} /> Delete
              </button>
              <button className="menu-item" onClick={() => setConfirm(false)}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                className="menu-item"
                onClick={() => {
                  setTitle(displayTitle(chat.title));
                  setRenaming(true);
                  setMenu(false);
                }}
              >
                <Pencil size={14} /> Rename
              </button>
              <button className="menu-item is-danger" onClick={() => setConfirm(true)}>
                <Trash2 size={14} /> Delete…
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function Sidebar(p: Props) {
  const { profile, logout } = useAuth();
  const sentinel = useRef<HTMLDivElement>(null);
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || !p.hasMore) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && p.onLoadMore());
    io.observe(el);
    return () => io.disconnect();
  }, [p.hasMore, p.onLoadMore]);

  const groups = p.query ? [{ label: p.searching ? "Searching…" : "Results", items: p.chats }] : groupChats(p.chats);
  const name = [profile?.firstName, profile?.lastName].filter(Boolean).join(" ") || profile?.email || "Your account";
  const initials = (profile?.firstName?.[0] ?? profile?.email?.[0] ?? "?").toUpperCase();
  const plan = p.subscription?.plan.name;

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <Link to="/" className="sidebar-logo" onClick={p.onClose}>
          <Logo size={20} />
        </Link>
        <button className="icon-btn sidebar-close" onClick={p.onClose} aria-label="Close sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="sidebar-actions">
        <button className="btn btn--new" onClick={p.onNew}>
          <Plus size={16} />
          New research
          <kbd className="kbd-hint">{isMac ? "⌘" : "Ctrl"} ⇧ O</kbd>
        </button>
        <label className="search">
          <Search size={15} />
          <input
            ref={p.searchRef}
            value={p.query}
            onChange={(e) => p.setQuery(e.target.value)}
            placeholder="Search chats"
            dir="auto"
            onKeyDown={(e) => e.key === "Escape" && p.setQuery("")}
          />
          {p.query ? (
            <button className="icon-btn icon-btn--sm" onClick={() => p.setQuery("")} aria-label="Clear search">
              <X size={13} />
            </button>
          ) : (
            <kbd className="kbd-hint">{isMac ? "⌘" : "Ctrl"} K</kbd>
          )}
        </label>
      </div>

      <nav className="chat-list" aria-label="Chats">
        {groups.map((g) => (
          <section key={g.label} className="chat-group">
            <h3 className="mono-label">{g.label}</h3>
            {g.items.map((c) => (
              <ChatRow key={c.uuid} chat={c} onRename={p.onRename} onDelete={p.onDelete} onNavigate={p.onClose} />
            ))}
          </section>
        ))}
        {!p.chats.length && !p.searching && (
          <p className="chat-empty">{p.query ? "No chats match that search." : "Your research will show up here."}</p>
        )}
        <div ref={sentinel} />
      </nav>

      <div className="sidebar-foot">
        <Link to="/plans" className="plan-card" onClick={p.onClose}>
          <Gauge size={15} />
          <span>
            <strong>{plan ? `${plan.charAt(0)}${plan.slice(1).toLowerCase()} plan` : "Plans"}</strong>
            <small>{p.subscription ? `${p.subscription.plan.daily_message_limit} messages a day` : "See limits and upgrade"}</small>
          </span>
        </Link>
        <div className="account">
          <span className="avatar">{initials}</span>
          <span className="account-name" title={profile?.email}>
            {name}
          </span>
          <button className="icon-btn icon-btn--sm" onClick={logout} title="Sign out" aria-label="Sign out">
            <LogOut size={15} />
          </button>
        </div>
        <ThemeSwitch />
      </div>
    </aside>
  );
}
