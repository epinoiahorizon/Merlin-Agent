import { AlternateScreen, render } from '@merlin/ink'
import React from 'react'

import { fromSkin } from '../../theme.js'

import { applyPalette, OperatorConsoleV6, paletteFromTheme } from './operator-console-v6.js'
import { loadActiveSkin } from './skinLoader.js'

// Paint the demo with the ACTIVE CLI skin when one resolves locally;
// otherwise keep the static Arcane sample palette.
const skin = loadActiveSkin()

if (skin) {
  const theme = fromSkin(skin.colors, skin.branding, '', '', skin.toolPrefix ?? '', skin.branding.help_header ?? '')

  applyPalette(paletteFromTheme(theme, skin.colors['background']))
}

render(
  <AlternateScreen>
    <OperatorConsoleV6 />
  </AlternateScreen>
)
