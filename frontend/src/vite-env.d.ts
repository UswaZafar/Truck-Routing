/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API origin when the frontend is hosted separately (empty = same origin / Vite proxy). */
  readonly VITE_API_BASE_URL?: string
}
