import '@fontsource-variable/urbanist'
import './styles.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from './api/client'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Client errors (4xx) and rate limits won't fix themselves; retry only flaky server/network errors once.
      retry: (failureCount, error) =>
        failureCount < 1 && error instanceof ApiError && (error.status === 0 || error.status === 502),
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
