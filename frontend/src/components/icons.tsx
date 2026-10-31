// Small stroke icons; decorative, so hidden from assistive technology (the surrounding text names them).
const icon = { width: 16, height: 16, viewBox: '0 0 16 16', fill: 'none', 'aria-hidden': true, focusable: false } as const
const stroke = { stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

export const WindIcon = () => (
  <svg {...icon}>
    <path {...stroke} d="M2 6h7.5a2 2 0 1 0-2-2M2 10h10a2 2 0 1 1-2 2" />
  </svg>
)

export const RainIcon = () => (
  <svg {...icon}>
    <path {...stroke} d="M8 2C6.3 4.9 4.5 6.9 4.5 9.5a3.5 3.5 0 0 0 7 0C11.5 6.9 9.7 4.9 8 2z" />
  </svg>
)

export const SnowIcon = () => (
  <svg {...icon}>
    <path {...stroke} d="M8 1.5v13M2.4 4.75l11.2 6.5M2.4 11.25l11.2-6.5" />
  </svg>
)

export const SwapIcon = () => (
  <svg {...icon}>
    <path {...stroke} d="M5 2.5v11M2.5 11 5 13.5 7.5 11M11 13.5v-11M8.5 5 11 2.5 13.5 5" />
  </svg>
)

export const EditIcon = () => (
  <svg {...icon}>
    <path {...stroke} d="M3 13l.8-3.2L10.6 3a1.4 1.4 0 0 1 2 0l.4.4a1.4 1.4 0 0 1 0 2L6.2 12.2zM9.5 4.1l2.4 2.4" />
  </svg>
)

export const PlayIcon = () => (
  <svg {...icon}>
    <path d="M5 3.2v9.6a.6.6 0 0 0 .9.5l7.6-4.8a.6.6 0 0 0 0-1L5.9 2.7a.6.6 0 0 0-.9.5z" fill="currentColor" />
  </svg>
)

export const PauseIcon = () => (
  <svg {...icon}>
    <path d="M4.5 3h2.2v10H4.5zM9.3 3h2.2v10H9.3z" fill="currentColor" />
  </svg>
)

export const TruckIcon = () => (
  <svg width="22" height="16" viewBox="0 0 22 16" fill="none" aria-hidden="true" focusable="false">
    <path {...stroke} d="M1.5 3.5h11v8h-11zM12.5 6.5h4l3 3v2h-7z" />
    <circle cx="5" cy="12.5" r="1.8" fill="currentColor" />
    <circle cx="16" cy="12.5" r="1.8" fill="currentColor" />
  </svg>
)

/** App mark: three routes leaving one origin, the chosen one solid. */
export const BrandMark = () => (
  <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true" focusable="false">
    <rect width="34" height="34" rx="11" fill="#15171C" />
    <path d="M9 25c4-1 6-6 8-10s5-6 8-6" stroke="#FFFFFF" strokeWidth="2.6" fill="none" strokeLinecap="round" />
    <path d="M9 25c6 0 9-3 16-3" stroke="#8C919B" strokeWidth="2" fill="none" strokeLinecap="round" />
    <circle cx="9" cy="25" r="2.6" fill="#FFFFFF" />
    <circle cx="25" cy="9" r="2.6" fill="#E8B10E" />
  </svg>
)
