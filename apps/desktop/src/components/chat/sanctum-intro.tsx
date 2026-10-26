import { loadComposerDraft } from '@/store/composer'

import type { IntroProps } from './intro'
import { SanctumCrest } from './sanctum-crest'

/**
 * ᛟ The Sanctum splash — the empty transcript under the Sanctum skin.
 *
 * Same contract as `Intro` (personality + seed → the configured voice), but it
 * speaks in the app's own chrome: a gilt crest, the rotating headline in the
 * display face, and four plates that load a real prompt into the composer.
 *
 * The plates write a DRAFT rather than sending: the arcane frame should never
 * fire a turn the user hasn't read. The tokens all come from the active theme,
 * so this renders correctly under any skin, not only the one it was cut for.
 */
type Plate = {
  numeral: string
  rune: string
  title: string
  headline: string
  blurb: string
  prompt: string
  tone: 'gold' | 'cyan' | 'ember' | 'moss'
}

const PLATES: Plate[] = [
  {
    numeral: 'I',
    rune: 'ᛟ',
    title: 'The Reliquary of Avalon',
    headline: "Merlin's runic cap, staff & living scroll",
    blurb: 'Rotate the crown, the channeling staff and the unfurling record',
    prompt:
      'Open the Reliquary of Avalon and walk me through the four relics — the runic cap, the staff, the living scroll and the scrying orb — and what each one is for.',
    tone: 'gold'
  },
  {
    numeral: 'II',
    rune: 'ᛏ',
    title: 'Merlin agent harness',
    headline: 'Autonomous grimoire fleet blueprint',
    blurb: 'Inspect the orchestrator, the previs guild and the sub-agent runes',
    prompt:
      'Show me the Merlin agent harness: the orchestrator, each sub-agent guild, and exactly how a task is dispatched and verified.',
    tone: 'cyan'
  },
  {
    numeral: 'III',
    rune: 'ᛉ',
    title: 'Solarized mana ledger',
    headline: 'Simulate astral compute & ley-lines',
    blurb: 'Balance GPU shrines, context depth and fleet concurrency',
    prompt:
      'Open the Solarized mana ledger and help me balance GPU shrines, context depth and fleet concurrency for this machine.',
    tone: 'ember'
  },
  {
    numeral: 'IV',
    rune: 'ᛋ',
    title: 'Illuminated decree',
    headline: 'The concordat of Epinoia & Avalon',
    blurb: 'A ceremonial manuscript with drop caps, wax seals and runic law',
    prompt:
      'Draft the illuminated decree that fixes the Solarized laws of this sanctuary: light and dark polarities, gold gilding, and the runic marks.',
    tone: 'moss'
  }
]

/**
 * The sanctum's own greeting. The stock intro rotation is written for a
 * developer shell ("Stdin open", "Shell mounted. Awaiting input.") — as the
 * first thing an Archmage sees it reads like a terminal, not a sanctum.
 */
function sanctumGreeting(): string {
  const hour = new Date().getHours()

  if (hour < 11) {
    return 'Hail at dawn, Archmage'
  }

  if (hour < 17) {
    return 'Well met this solar hour'
  }

  if (hour < 21) {
    return 'Greetings at eventide'
  }

  return 'Greetings under the astral watch'
}

const SANCTUM_QUOTE =
  'Speak your command; the Staff of Merlin shall channel the astral threads and unfurl living relics in Solarized harmony.'

export function SanctumIntro(_props: IntroProps) {
  const headline = sanctumGreeting()
  const body = SANCTUM_QUOTE

  return (
    <div className="si" data-slot="sanctum-intro">
      <div className="si__crest">
        <SanctumCrest className="si__crestSvg" />
      </div>

      <div className="si__eyebrow">
        <span aria-hidden="true">ᛟ</span>
        <span>Epinoia Horizon · Solarized Sanctum</span>
        <span aria-hidden="true">ᛟ</span>
      </div>

      <h1 className="si__title">{headline}</h1>
      <p className="si__quote">{body}</p>

      <div className="si__plates">
        {PLATES.map(plate => (
          <button
            className={`si__plate si__plate--${plate.tone}`}
            key={plate.numeral}
            onClick={() => loadComposerDraft(plate.prompt)}
            type="button"
          >
            <span className="si__plateHead">
              <span aria-hidden="true" className="si__rune">
                {plate.rune}
              </span>
              <span>
                {plate.numeral}. {plate.title}
              </span>
            </span>
            <span className="si__plateTitle">{plate.headline}</span>
            <span className="si__plateBlurb">{plate.blurb}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
