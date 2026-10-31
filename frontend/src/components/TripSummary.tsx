import { formatClock, formatPounds, formatWeekday, splitPlace } from '../lib/format'
import { EditIcon, TruckIcon } from './icons'

interface Props {
  origin: string
  destination: string
  departureAt: string
  /** Arrival of the selected route, once planned. */
  arrivalAt?: string
  loadLb: number
  intervalMiles: number
  busy: boolean
  onEdit: () => void
}

/** The submitted trip as a journey line: origin and departure on the left, destination and arrival on the right. */
export function TripSummary({ origin, destination, departureAt, arrivalAt, loadLb, intervalMiles, busy, onEdit }: Props) {
  const [fromCity, fromRest] = splitPlace(origin)
  const [toCity, toRest] = splitPlace(destination)
  return (
    <section className="trip-summary" aria-label="Trip">
      <div className="journey">
        <div className="journey__end">
          <span className="journey__city" title={origin}>{fromCity}</span>
          {fromRest && <span className="journey__region">{fromRest}</span>}
          <span className="journey__time">
            {formatWeekday(departureAt)} {formatClock(departureAt)}
          </span>
        </div>
        <div className="journey__line" aria-hidden="true">
          <span className="journey__truck">
            <TruckIcon />
          </span>
        </div>
        <div className="journey__end journey__end--to">
          <span className="journey__city" title={destination}>{toCity}</span>
          {toRest && <span className="journey__region">{toRest}</span>}
          <span className="journey__time">
            {arrivalAt ? `${formatWeekday(arrivalAt)} ${formatClock(arrivalAt)}` : busy ? 'Planning…' : '—'}
          </span>
        </div>
      </div>
      <div className="trip-summary__foot">
        <span>
          {formatPounds(loadLb)} · checkpoint every {intervalMiles} mi
        </span>
        <button type="button" className="icon-button" onClick={onEdit} disabled={busy} aria-label="Edit trip">
          <EditIcon />
        </button>
      </div>
    </section>
  )
}
