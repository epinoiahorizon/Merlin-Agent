/**
 * ᛟ The runic cap of Merlin — the sanctum's marks.
 *
 * One SVG, two uses: the crest medallion on the empty transcript, and (via
 * `compact`) the small avatar the composer and plates share. It is drawn in
 * the palette's own tokens so it follows the active skin instead of pinning
 * indigo and gold into the DOM.
 */
export function SanctumCrest({ compact = false, className }: { compact?: boolean; className?: string }) {
  const hat = (
    <>
      <ellipse className="si-crest__shadow" cx="90" cy="143" rx="43" ry="8" />
      <path
        className="si-crest__body"
        d="M44 131c4-38 16-76 46-104 8-8 18-6 17 4-2 14-9 24-9 38 1 26 14 50 34 64-20 10-70 10-88-2z"
      />
      <path className="si-crest__rim" d="M46 126q43 15 82-3l2 9q-42 18-84 4z" />
      <g className="si-crest__runes">
        <path d="M82 57l4-16M84 47l-6-6M84 46l6-4" />
        <path d="M78 101l-2-19M70 90l7-9 8 8" />
        <path d="M95 84l5 9 6-2 5 9" />
        <path d="M88 110l8 6-5 8-8-6z" />
      </g>
    </>
  )

  if (compact) {
    return (
      <svg aria-hidden="true" className={className} data-slot="sanctum-crest" viewBox="0 0 180 180">
        {hat}
      </svg>
    )
  }

  return (
    <svg aria-hidden="true" className={className} data-slot="sanctum-crest" viewBox="0 0 180 180">
      <circle className="si-crest__ring" cx="90" cy="90" r="82" />
      <g className="si-crest__stars">
        <path d="M45 52l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" />
        <path d="M136 56l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" />
      </g>
      {hat}
    </svg>
  )
}
