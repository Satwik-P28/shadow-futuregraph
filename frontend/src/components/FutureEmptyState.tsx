export function FutureEmptyState() {
  return (
    <div className="relative" aria-hidden={false}>
      <svg viewBox="0 0 520 340" className="mx-auto h-44 w-full max-w-lg sm:h-auto" role="img" aria-label="Abstract branching futures">
        <g fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="1.2">
          <path d="M260 64 V128" />
          <path d="M260 128 C260 168 140 168 120 210" />
          <path d="M260 128 V214" />
          <path d="M260 128 C260 168 380 168 400 210" />
        </g>
        <g className="breathe">
          <circle cx="260" cy="52" r="7" fill="#8FB4C8" />
          <circle cx="120" cy="228" r="6" fill="#7EAE96" />
          <circle cx="260" cy="232" r="6" fill="#8E86A8" />
          <circle cx="400" cy="228" r="6" fill="#D37B6E" />
        </g>
        <g fill="#9AA3B2" fontFamily="Inter, sans-serif" fontSize="11" letterSpacing="1.6">
          <text x="260" y="36" textAnchor="middle">NOW</text>
          <text x="120" y="258" textAnchor="middle">✓</text>
          <text x="260" y="262" textAnchor="middle">?</text>
          <text x="400" y="258" textAnchor="middle">×</text>
        </g>
      </svg>
      <p className="mt-2 text-center text-sm text-mute">Shadow maps material futures, not every possible future.</p>
    </div>
  );
}
