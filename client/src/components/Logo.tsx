/** The DeepQuery mark: a prompt chevron next to a lens, from the original logo. */
export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="logo-mark">
      <path d="M2.5 7.5 6 11l-3.5 3.5" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="14.5" cy="10.5" r="5" stroke="var(--accent)" strokeWidth="2.4" />
      <path d="m18.2 14.4 3.3 4.6" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ size = 22 }: { size?: number }) {
  return (
    <span className="logo" style={{ fontSize: size * 0.82 }}>
      <LogoMark size={size} />
      <span className="logo-word">
        Deep<span className="logo-accent">Query</span>
      </span>
    </span>
  );
}
