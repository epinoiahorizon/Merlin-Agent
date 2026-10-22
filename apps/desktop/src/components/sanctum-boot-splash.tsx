import cosmosArt from '@/assets/sanctum-cosmos.webp'

/**
 * ᛟ The boot ceremony — the Sanctum skin's answer to the bare `LOADING` mark.
 *
 * `GatewayConnectingOverlay` already owns WHEN the app is allowed to paint the
 * session; this component only owns what the user stares at while it happens.
 * It reports the boot's own progress (`$desktopBoot.progress` / `.message`) so
 * the bar and the italic line under the title are the real boot narrative,
 * never a decorative animation that lies about how far along startup is.
 *
 * The emblem is the full relic — cap, channeling staff, orb — not the compact
 * crest the empty transcript uses: a boot screen has the room for it, and it is
 * the one moment the app can afford ceremony over utility.
 *
 * The backdrop is the sanctum's astral plate (`assets/sanctum-cosmos.webp`)
 * under a dark radial scrim: the artwork carries the edges, the scrim keeps the
 * crest, title and status legible no matter how the plate lands at a given
 * window size (a `cover` crop cannot be aligned to, so nothing here is
 * positioned against a feature of the image).
 */
export function SanctumBootSplash({
  leaving,
  progress,
  status
}: {
  /** The overlay is fading out — drop the content, keep the wash until it does. */
  leaving: boolean
  /** 0–100, from the desktop boot progress stream. */
  progress: number
  /** The boot step's own message (localized). */
  status: string
}) {
  // 4% floor: an empty track on the first frame reads as "stuck", not "starting".
  const percent = Math.min(100, Math.max(4, Math.round(progress)))

  return (
    <div
      aria-live="polite"
      className={leaving ? 'sbs sbs--leaving absolute inset-0' : 'sbs absolute inset-0'}
      data-slot="sanctum-boot"
      role="status"
      style={{ backgroundImage: `var(--sbs-scrim), url(${cosmosArt})` }}
    >
      <div aria-hidden="true" className="sbs__stars">
        <svg preserveAspectRatio="xMidYMid slice" viewBox="0 0 1000 700">
          <g className="sbs__starField">
            <path className="sbs__twinkle" d="M120 90l4 14 14 4-14 4-4 14-4-14-14-4 14-4z" />
            <path
              className="sbs__twinkle"
              d="M860 110l5 18 18 5-18 5-5 18-5-18-18-5 18-5z"
              style={{ animationDelay: '.6s' }}
            />
            <path
              className="sbs__twinkle"
              d="M210 260l3 10 10 3-10 3-3 10-3-10-10-3 10-3z"
              style={{ animationDelay: '1.2s' }}
            />
            <path
              className="sbs__twinkle"
              d="M780 280l4 14 14 4-14 4-4 14-4-14-14-4 14-4z"
              style={{ animationDelay: '.3s' }}
            />
            <path
              className="sbs__twinkle"
              d="M150 510l4 14 14 4-14 4-4 14-4-14-14-4 14-4z"
              style={{ animationDelay: '1.7s' }}
            />
            <path
              className="sbs__twinkle"
              d="M840 490l5 16 16 5-16 5-5 16-5-16-16-5 16-5z"
              style={{ animationDelay: '.9s' }}
            />
            <circle cx="280" cy="190" opacity=".85" r="2.5" />
            <circle cx="720" cy="210" opacity=".9" r="3" />
            <circle cx="190" cy="390" opacity=".7" r="2" />
            <circle cx="820" cy="380" opacity=".95" r="2.5" />
          </g>
        </svg>
      </div>

      <div className="sbs__inner">
        <svg aria-hidden="true" className="sbs__emblem" viewBox="0 0 260 260">
          <defs>
            <radialGradient cx="50%" cy="50%" id="sbs-halo" r="50%">
              <stop offset="0%" stopColor="#fff8d6" stopOpacity=".95" />
              <stop offset="45%" stopColor="#f5b800" stopOpacity=".6" />
              <stop offset="100%" stopColor="#002b36" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="sbs-hatBody" x1="20%" x2="86%" y1="8%" y2="92%">
              <stop offset="0%" stopColor="#1d4a70" />
              <stop offset="35%" stopColor="#0d2840" />
              <stop offset="78%" stopColor="#071c2e" />
              <stop offset="100%" stopColor="#040f1a" />
            </linearGradient>
            <linearGradient id="sbs-hatShine" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#8cc0e0" stopOpacity=".5" />
              <stop offset="100%" stopColor="#0d2840" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="sbs-runeGold" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#fff3b0" />
              <stop offset="50%" stopColor="#e6b800" />
              <stop offset="100%" stopColor="#9e7200" />
            </linearGradient>
          </defs>

          <circle cx="130" cy="130" fill="url(#sbs-halo)" r="116" />

          <g className="sbs__ring">
            <circle
              cx="130"
              cy="130"
              fill="none"
              opacity=".38"
              r="106"
              stroke="#002b36"
              strokeDasharray="6 5"
              strokeWidth="1.4"
            />
            <circle
              cx="130"
              cy="130"
              fill="none"
              opacity=".7"
              r="97"
              stroke="#fdf6e3"
              strokeDasharray="3 6"
              strokeWidth="1.1"
            />
            <circle cx="130" cy="23" fill="#fdf6e3" r="3.6" />
            <circle cx="130" cy="237" fill="#fdf6e3" r="3.6" />
            <circle cx="23" cy="130" fill="#2aa198" r="3.6" />
            <circle cx="237" cy="130" fill="#2aa198" r="3.6" />
          </g>

          <g className="sbs__float">
            <g transform="rotate(26 130 136)">
              <line stroke="#5c3a21" strokeLinecap="round" strokeWidth="6.5" x1="130" x2="130" y1="24" y2="236" />
              <line
                stroke="url(#sbs-runeGold)"
                strokeDasharray="10 9"
                strokeLinecap="round"
                strokeWidth="2.4"
                x1="130"
                x2="130"
                y1="24"
                y2="236"
              />
              <circle className="sbs__pulse" cx="130" cy="24" fill="#2aa198" r="12" />
              <polygon fill="#fdf6e3" points="130,6 139,24 130,38 121,24" stroke="#b58900" strokeWidth="1.8" />
            </g>

            <ellipse cx="130" cy="207" fill="rgba(0,43,54,.5)" rx="62" ry="13" />
            <path
              d="M68 192C72 152 84 104 106 66c12-20 30-32 44-34 9-1 13 5 7 15-6 9-12 19-11 33 2 30 18 68 42 104 6 9-2 19-20 23-24 6-62 6-88-2-11-4-14-8-12-13z"
              fill="url(#sbs-hatBody)"
              stroke="#04101c"
              strokeWidth="2"
            />
            <path d="M92 115c12-37 30-67 55-79 6-2 8 2 2 10-11 12-23 38-31 72z" fill="url(#sbs-hatShine)" />
            <path d="M69 184q61 20 117-3l3 12q-61 22-123 2z" fill="url(#sbs-runeGold)" opacity=".95" />
            <path
              d="M75 189q17 6 30 3M115 194q15 5 31 1M156 193q14-3 26-7"
              fill="none"
              stroke="#071c2e"
              strokeLinecap="round"
              strokeWidth="2.1"
            />

            <g
              className="sbs__glow"
              fill="none"
              stroke="url(#sbs-runeGold)"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="3"
            >
              <path d="M118 84l5-21M121 72l-7-8M121 70l8-5" />
              <path d="M138 69v12l-7 1" />
              <polygon points="103,92 109,98 103,106 97,100" />
              <path d="M129 108l-2-10 11-2 2 8" />
              <path d="M112 146l-3-27M101 130l8-11 10 9" />
              <path d="M136 122l7 13 8-3 7 14" />
              <polygon points="126,154 138,162 131,173 119,165" />
              <path d="M131 173l-6 9M119 165l20 13" />
              <path d="M88 156l2 12 7-2 2 13" />
              <path d="M164 152c-5 8-3 19 5 21" />
            </g>
          </g>
        </svg>

        <p className="sbs__eyebrow">
          <span aria-hidden="true">ᛟ</span>
          <span>Epinoia Horizon · Solarized Sanctum</span>
          <span aria-hidden="true">ᛟ</span>
        </p>

        <h1 className="sbs__title">
          Awakening the
          <br />
          Merlin Scroll
        </h1>

        <p className="sbs__status">{status}</p>

        <div aria-valuemax={100} aria-valuemin={0} aria-valuenow={percent} className="sbs__bar" role="progressbar">
          <i style={{ width: `${percent}%` }} />
        </div>
      </div>
    </div>
  )
}
