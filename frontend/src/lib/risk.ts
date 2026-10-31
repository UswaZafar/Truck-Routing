import type { RiskKey } from '../api/types'

export interface RiskMeta {
  key: RiskKey
  label: string
  /** Map marks, heatmap and risk lines. */
  color: string
  /** rgb triple for canvas rendering */
  rgb: [number, number, number]
  /** Chip background and text (4.5:1 or better). */
  tint: string
  ink: string
}

// Order matters: index = risk score (Low 0 … No Travel 4), same as the backend.
// The interface itself is neutral, so these are the only strong colours on screen.
export const RISK_LEVELS: readonly RiskMeta[] = [
  { key: 'low', label: 'Low', color: '#3E9B6A', rgb: [62, 155, 106], tint: '#E3F2E9', ink: '#1F6B43' },
  { key: 'moderate', label: 'Moderate', color: '#E8B10E', rgb: [232, 177, 14], tint: '#FCF1CC', ink: '#6E5200' },
  { key: 'high', label: 'High', color: '#EF7A1A', rgb: [239, 122, 26], tint: '#FDE6D2', ink: '#8A3F00' },
  { key: 'severe', label: 'Severe', color: '#D93A2B', rgb: [217, 58, 43], tint: '#FADBD7', ink: '#9B1F14' },
  { key: 'no_travel', label: 'No Travel', color: '#6E2BB8', rgb: [110, 43, 184], tint: '#6E2BB8', ink: '#FFFFFF' },
]

const BY_KEY = Object.fromEntries(RISK_LEVELS.map((level) => [level.key, level])) as Record<RiskKey, RiskMeta>

export const riskMeta = (key: RiskKey): RiskMeta => BY_KEY[key]
