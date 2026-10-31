const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const time = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
const clock = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
const weekday = new Intl.DateTimeFormat(undefined, { weekday: 'short' })

export const formatDateTime = (iso: string | Date): string => dateTime.format(new Date(iso))
export const formatTime = (iso: string | Date): string => time.format(new Date(iso))
export const formatClock = (iso: string | Date): string => clock.format(new Date(iso))
export const formatWeekday = (iso: string | Date): string => weekday.format(new Date(iso))

/** Short name of the browser's time zone, e.g. "MDT" or "GMT+5". */
export function timeZoneName(date = new Date()): string {
  const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(date)
  return parts.find((part) => part.type === 'timeZoneName')?.value ?? ''
}

/** "Denver, Colorado, United States" → ["Denver", "Colorado, United States"]. */
export function splitPlace(label: string): [string, string] {
  const comma = label.indexOf(',')
  return comma === -1 ? [label, ''] : [label.slice(0, comma), label.slice(comma + 1).trim()]
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${minutes}m`
}

export const formatMiles = (miles: number, digits = 0): string =>
  `${miles.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })} mi`

export const formatPounds = (lb: number): string => `${lb.toLocaleString()} lb`

/** Value for <input type="datetime-local"> in the browser's time zone. */
export function toDateTimeLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function nextFullHour(now = new Date()): Date {
  const next = new Date(now)
  next.setMinutes(0, 0, 0)
  next.setHours(next.getHours() + 1)
  return next
}
