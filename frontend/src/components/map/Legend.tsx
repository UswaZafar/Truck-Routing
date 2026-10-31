import type { CSSProperties } from 'react'

import { RISK_LEVELS } from '../../lib/risk'

export function Legend() {
  return (
    <ul className="map-legend" aria-label="Risk levels">
      {RISK_LEVELS.map((level) => (
        <li key={level.key} className={`map-legend__item map-legend__item--${level.key}`} style={{ '--dot': level.color } as CSSProperties}>
          {level.label}
        </li>
      ))}
    </ul>
  )
}
