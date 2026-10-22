import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'
import * as composer from '@/store/composer'

import { SanctumIntro } from './sanctum-intro'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderSanctum(personalty?: string) {
  vi.spyOn(Math, 'random').mockReturnValue(0)

  return render(
    <I18nProvider configClient={null} initialLocale="en">
      <SanctumIntro personality={personalty} seed={0} />
    </I18nProvider>
  )
}

it('renders the crest, the rotating headline and one plate per relic', () => {
  const { container } = renderSanctum()

  expect(container.querySelector('[data-slot="sanctum-intro"]')).toBeTruthy()
  expect(container.querySelectorAll('.si-crest__body')).toHaveLength(1)
  expect(container.querySelectorAll('.si__plate')).toHaveLength(4)
  expect(container.querySelector('.si__title')?.textContent?.trim()).toBeTruthy()
  expect(container.querySelector('.si__quote')?.textContent?.trim()).toBeTruthy()
})

it('loads a plate prompt into the composer as a DRAFT, never as a send', () => {
  const setDraft = vi.spyOn(composer, 'loadComposerDraft').mockImplementation(() => true)
  const { container } = renderSanctum()
  const plates = container.querySelectorAll<HTMLButtonElement>('.si__plate')

  fireEvent.click(plates[1])

  expect(setDraft).toHaveBeenCalledTimes(1)
  expect(setDraft.mock.calls[0][0]).toContain('Merlin agent harness')
})

it('gives every plate a distinct prompt so the relic order stays meaningful', () => {
  const setDraft = vi.spyOn(composer, 'loadComposerDraft').mockImplementation(() => true)
  const { container } = renderSanctum()
  const plates = container.querySelectorAll<HTMLButtonElement>('.si__plate')

  plates.forEach(plate => fireEvent.click(plate))

  const prompts = setDraft.mock.calls.map(call => call[0])
  expect(new Set(prompts).size).toBe(4)
})
