import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import { SanctumBootSplash } from './sanctum-boot-splash'

afterEach(cleanup)

it('renders the relic, the ceremony title and the boot step it is on', () => {
  const { container, getByText } = render(
    <SanctumBootSplash leaving={false} progress={42} status="Starting the Merlin gateway…" />
  )

  expect(container.querySelector('[data-slot="sanctum-boot"]')).toBeTruthy()
  // The full emblem (cap + staff + orb), not the compact transcript crest.
  expect(container.querySelectorAll('.sbs__float')).toHaveLength(1)
  expect(container.querySelectorAll('.sbs__pulse')).toHaveLength(1)
  expect(getByText(/Awakening the/)).toBeTruthy()
  expect(getByText('Starting the Merlin gateway…')).toBeTruthy()
})

it('drives the bar from real boot progress, with a floor on the first frame', () => {
  const { container, rerender } = render(<SanctumBootSplash leaving={false} progress={0} status="Booting" />)
  const bar = () => container.querySelector<HTMLElement>('.sbs__bar > i')

  // An empty track reads as "stuck"; the first frame still shows a sliver.
  expect(container.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('4')
  expect(bar()?.style.width).toBe('4%')

  rerender(<SanctumBootSplash leaving={false} progress={100} status="Ready" />)

  expect(container.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('100')
  expect(bar()?.style.width).toBe('100%')
})

it('drops the content while leaving so the wash can fade on its own', () => {
  const { container } = render(<SanctumBootSplash leaving progress={100} status="Ready" />)

  expect(container.querySelector('.sbs--leaving')).toBeTruthy()
})
