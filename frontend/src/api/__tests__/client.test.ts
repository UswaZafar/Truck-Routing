import { describe, expect, it } from 'vitest'

import { ApiError } from '../client'

describe('ApiError.fromResponse', () => {
  it('keeps DRF field errors, flattening nested ones', () => {
    const error = ApiError.fromResponse(400, {
      load_weight_lb: ['Ensure this value is less than or equal to 80000.'],
      origin: { lat: ['Ensure this value is less than or equal to 90.'] },
    })
    expect(error.status).toBe(400)
    expect(error.fieldErrors).toEqual({
      load_weight_lb: 'Ensure this value is less than or equal to 80000.',
      origin: 'lat: Ensure this value is less than or equal to 90.',
    })
    expect(error.message).toBe('Ensure this value is less than or equal to 80000.')
  })

  it('uses detail + code for non-field errors', () => {
    const error = ApiError.fromResponse(503, { detail: 'Weather service rate limit reached.', code: 'upstream_error' })
    expect(error.message).toBe('Weather service rate limit reached.')
    expect(error.code).toBe('upstream_error')
  })
})
