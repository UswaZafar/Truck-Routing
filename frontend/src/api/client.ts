const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** An API failure with DRF field errors flattened to `{ field: message }`. */
export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fieldErrors = fieldErrors
  }

  static fromResponse(status: number, body: unknown): ApiError {
    if (body && typeof body === 'object') {
      const record = body as Record<string, unknown>
      if (typeof record.detail === 'string') {
        return new ApiError(status, record.detail, {}, typeof record.code === 'string' ? record.code : undefined)
      }
      const fieldErrors = flattenErrors(record)
      const first = Object.values(fieldErrors)[0]
      if (first) return new ApiError(status, first, fieldErrors, 'invalid')
    }
    return new ApiError(status, `Request failed (${status}).`)
  }
}

function flattenErrors(errors: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [field, value] of Object.entries(errors)) {
    if (Array.isArray(value) && typeof value[0] === 'string') out[field] = value[0]
    else if (value && typeof value === 'object') {
      // Nested serializer errors, e.g. { origin: { lat: ["…"] } } → origin: "lat: …"
      const nested = Object.entries(flattenErrors(value as Record<string, unknown>))[0]
      if (nested) out[field] = `${nested[0]}: ${nested[1]}`
    }
  }
  return out
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw ApiError.fromResponse(response.status, body)
  return body as T
}
