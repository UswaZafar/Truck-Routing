import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { apiFetch } from './client'
import type { Heatmap, Place, TripPlan, TripRequest } from './types'

const MIN_QUERY_LENGTH = 3
const GEOCODE_DEBOUNCE_MS = 300

/** Place suggestions for what the user is typing (debounced, cached per query). */
export function useGeocode(text: string) {
  const query = useDebouncedValue(text.trim(), GEOCODE_DEBOUNCE_MS)
  return useQuery<Place[], Error>({
    queryKey: ['geocode', query.toLowerCase()],
    queryFn: ({ signal }) =>
      apiFetch<{ results: Place[] }>(`/api/geocode/?q=${encodeURIComponent(query)}`, { signal }).then(
        (body) => body.results,
      ),
    enabled: query.length >= MIN_QUERY_LENGTH,
    staleTime: 24 * 60 * 60 * 1000,
    placeholderData: keepPreviousData,
  })
}

/**
 * The trip plan for the submitted inputs. Keyed by the inputs, so submitting the same trip again is served
 * from cache instead of re-running the (expensive) routing + weather pipeline.
 */
export function useTripPlan(request: TripRequest | null) {
  return useQuery({
    queryKey: ['trip-plan', request],
    queryFn: ({ signal }) =>
      apiFetch<TripPlan>('/api/trip-plans/', { method: 'POST', body: JSON.stringify(request), signal }),
    enabled: request !== null,
    staleTime: 10 * 60 * 1000,
    retry: false, // the server already retries the routing provider; a failed plan is shown with a retry button
  })
}

/**
 * Corridor heatmap for a plan; immutable once computed. Deliberately not abortable: the server finishes the
 * computation (and its weather calls) anyway, and an abortable query is cancelled and re-sent whenever its
 * component remounts (e.g. StrictMode's double mount), doubling the weather API usage.
 */
export function useHeatmap(planId: string | undefined) {
  return useQuery({
    queryKey: ['heatmap', planId],
    queryFn: () => apiFetch<Heatmap>(`/api/trip-plans/${planId}/heatmap/`),
    enabled: planId !== undefined,
    staleTime: Infinity,
  })
}
