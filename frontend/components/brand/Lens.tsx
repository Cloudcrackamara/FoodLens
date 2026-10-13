import { cn } from "@/lib/utils";

/**
 * The FoodLens lens: an SVG magnifier with a slow breathing glow (D105). Pure CSS animation,
 * no JavaScript; it stops under prefers-reduced-motion and breathes faster while a lookup on
 * the same page is running. Decorative only, so it is hidden from screen readers.
 *
 * `hero` is the large landing-page lens: the glass carries an adire pattern (Yoruba indigo
 * resist-dyed cloth motifs) and an illustrated shopper in a gele who checks a food pack through
 * a small magnifier. The rim and pattern stay faint; the shopper is drawn in `.lens-person` so
 * the page can show her more strongly where she does not sit behind text.
 */
export function Lens({ className, hero = false }: { className?: string; hero?: boolean }) {
  const id = hero ? "lens-hero" : "lens-plain";
  return (
    <svg
      viewBox="0 0 200 200"
      aria-hidden="true"
      focusable="false"
      className={cn("pointer-events-none select-none overflow-visible", className)}
    >
      <defs>
        <radialGradient id={`${id}-glow`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--coral)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="var(--coral)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-glass`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--coral)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.14" />
        </linearGradient>
        {hero && (
          <>
            <clipPath id={`${id}-clip`}>
              <circle cx="84" cy="84" r="49" />
            </clipPath>
            {/* One 16-unit adire tile: a ringed "eye" with a centre dot, corner dots and stitches. */}
            <pattern id={`${id}-adire`} width="16" height="16" patternUnits="userSpaceOnUse">
              <circle cx="8" cy="8" r="4.6" fill="none" stroke="var(--primary)" strokeWidth="1.1" />
              <circle cx="8" cy="8" r="1.6" fill="var(--primary)" />
              <circle cx="0" cy="0" r="1" fill="var(--primary)" />
              <circle cx="16" cy="0" r="1" fill="var(--primary)" />
              <circle cx="0" cy="16" r="1" fill="var(--primary)" />
              <circle cx="16" cy="16" r="1" fill="var(--primary)" />
              <path
                d="M8 0v1.6M8 14.4V16M0 8h1.6M14.4 8H16"
                stroke="var(--coral)"
                strokeWidth="1.1"
                strokeLinecap="round"
              />
            </pattern>
            {/* Small ankara-style dots for the blouse. */}
            <pattern id={`${id}-ankara`} width="6" height="6" patternUnits="userSpaceOnUse">
              <circle cx="3" cy="3" r="1.1" fill="var(--primary)" opacity="0.55" />
            </pattern>
          </>
        )}
      </defs>
      <circle className="lens-glow lens-faint" cx="84" cy="84" r="80" fill={`url(#${id}-glow)`} />
      <g className="lens-body">
        <g className="lens-faint">
          <line
            x1="130"
            y1="130"
            x2="176"
            y2="176"
            stroke="var(--primary)"
            strokeWidth="16"
            strokeLinecap="round"
          />
          <circle cx="84" cy="84" r="54" fill="var(--card)" />
          <circle cx="84" cy="84" r="54" fill={`url(#${id}-glass)`} />
          {hero && (
            <rect
              x="30"
              y="30"
              width="108"
              height="108"
              fill={`url(#${id}-adire)`}
              clipPath={`url(#${id}-clip)`}
              opacity="0.3"
            />
          )}
        </g>

        {hero && (
          <g className="lens-person" clipPath={`url(#${id}-clip)`}>
            {/* Shoulders and ankara blouse */}
            <path d="M44 140c2-22 16-32 34-32s32 10 34 32z" fill="var(--coral)" />
            <path d="M44 140c2-22 16-32 34-32s32 10 34 32z" fill={`url(#${id}-ankara)`} />
            {/* Neck */}
            <path d="M72 96h12v14c-2 3-10 3-12 0z" fill="var(--skin)" />
            {/* Head, turned towards the pack */}
            <ellipse cx="78" cy="82" rx="14" ry="16" fill="var(--skin)" />
            {/* Gele (head tie) with a coral fold */}
            <path
              d="M60 76c-4-14 8-26 22-25 12 0 22 8 20 18-6-4-14-6-22-5-8 1-14 5-20 12z"
              fill="var(--primary)"
            />
            <path d="M64 63c8-6 22-8 34-2" fill="none" stroke="var(--coral)" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M96 58c6-6 12-4 12 2-4-1-8 0-12-2z" fill="var(--primary)" />
            {/* Eye (blinks) and brow, looking right */}
            <ellipse className="lens-blink" cx="86" cy="81" rx="2" ry="2.2" fill="var(--ink-dark)" />
            <path d="M82 76.5q4-2 7 0" fill="none" stroke="var(--ink-dark)" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M89 90q-3 1.6-6 0" fill="none" stroke="var(--ink-dark)" strokeWidth="1.1" strokeLinecap="round" />
            {/* Food pack held up in the right hand */}
            <rect x="104" y="80" width="15" height="21" rx="2" fill="var(--card)" stroke="var(--primary)" strokeWidth="1.4" />
            <path d="M107 86h9M107 90h6M107 95h8" stroke="var(--primary)" strokeWidth="1.2" strokeLinecap="round" />
            <ellipse cx="110" cy="103" rx="5" ry="4" fill="var(--skin)" />
            {/* Small magnifier sweeping across the pack */}
            <g className="lens-scan">
              <line x1="100" y1="100" x2="94" y2="112" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" />
              <circle cx="103" cy="92" r="7" fill="var(--card)" fillOpacity="0.45" stroke="var(--primary)" strokeWidth="2.2" />
              <ellipse cx="93" cy="113" rx="4.5" ry="3.5" fill="var(--skin)" />
            </g>
          </g>
        )}

        <circle className="lens-faint" cx="84" cy="84" r="54" fill="none" stroke="var(--primary)" strokeWidth="10" />
        <path
          className="lens-faint"
          d="M56 70a32 32 0 0 1 24-24"
          fill="none"
          stroke="var(--card)"
          strokeWidth="7"
          strokeLinecap="round"
          opacity="0.9"
        />
      </g>
    </svg>
  );
}
