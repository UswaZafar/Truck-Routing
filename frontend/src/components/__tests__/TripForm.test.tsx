import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { TripForm } from '../TripForm'

function renderForm(props: Partial<Parameters<typeof TripForm>[0]> = {}) {
  const onSubmit = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <TripForm onSubmit={onSubmit} submitting={false} serverError={null} {...props} />
    </QueryClientProvider>,
  )
  return { onSubmit }
}

describe('TripForm', () => {
  it('blocks submission and shows field errors when required fields are missing', async () => {
    const { onSubmit } = renderForm()
    await userEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getAllByText('Required.')).toHaveLength(3) // origin, destination, load
  })

  it('submits typed places as text with the chosen interval', async () => {
    const { onSubmit } = renderForm()
    await userEvent.type(screen.getByLabelText('Origin'), 'Dallas, TX')
    await userEvent.type(screen.getByLabelText('Destination'), 'Houston, TX')
    await userEvent.type(screen.getByLabelText('Load weight (lb)'), '42000')
    await userEvent.click(screen.getByLabelText('10 mi'))
    await userEvent.click(screen.getByRole('button', { name: 'Plan routes' }))

    expect(onSubmit).toHaveBeenCalledOnce()
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      origin: 'Dallas, TX',
      destination: 'Houston, TX',
      load_weight_lb: 42000,
      interval_miles: 10,
    })
  })

  it('rejects an out-of-range load like the API does', async () => {
    const { onSubmit } = renderForm()
    await userEvent.type(screen.getByLabelText('Origin'), 'Dallas')
    await userEvent.type(screen.getByLabelText('Destination'), 'Houston')
    await userEvent.type(screen.getByLabelText('Load weight (lb)'), '90000')
    await userEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Enter a weight between 0 and 80,000 lb.')).toBeTruthy()
  })

  it('swaps origin and destination', async () => {
    renderForm()
    await userEvent.type(screen.getByLabelText('Origin'), 'Dallas')
    await userEvent.type(screen.getByLabelText('Destination'), 'Houston')
    await userEvent.click(screen.getByRole('button', { name: 'Swap origin and destination' }))
    expect((screen.getByLabelText('Origin') as HTMLInputElement).value).toBe('Houston')
    expect((screen.getByLabelText('Destination') as HTMLInputElement).value).toBe('Dallas')
  })

  it('shows server field errors under the matching input', () => {
    renderForm({ serverError: new ApiError(400, 'x', { origin: 'No place found for "Atlantis".' }) })
    expect(screen.getByText('No place found for "Atlantis".')).toBeTruthy()
  })
})
