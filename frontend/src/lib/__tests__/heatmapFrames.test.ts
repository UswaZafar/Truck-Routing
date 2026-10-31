import { describe, expect, it } from 'vitest'

import type { Heatmap } from '../../api/types'
import { buildHeatmapFrames, colorForIndex } from '../heatmapFrames'
import { RISK_LEVELS } from '../risk'

describe('colorForIndex', () => {
  it('uses the exact risk colour of each band', () => {
    expect(colorForIndex(0).slice(0, 3)).toEqual(RISK_LEVELS[0].rgb)
    expect(colorForIndex(15).slice(0, 3)).toEqual(RISK_LEVELS[1].rgb)
    expect(colorForIndex(29).slice(0, 3)).toEqual(RISK_LEVELS[2].rgb)
    expect(colorForIndex(30).slice(0, 3)).toEqual(RISK_LEVELS[3].rgb)
    expect(colorForIndex(40).slice(0, 3)).toEqual(RISK_LEVELS[4].rgb)
  })

  it('gets more opaque as risk rises', () => {
    const alphas = [0, 9, 10, 25, 35, 40].map((v) => colorForIndex(v)[3])
    expect([...alphas].sort((a, b) => a - b)).toEqual(alphas)
  })
})

const pixel = (frame: Uint8ClampedArray, width: number, x: number, y: number) =>
  Array.from(frame.slice((y * width + x) * 4, (y * width + x) * 4 + 4))

describe('buildHeatmapFrames', () => {
  const grid = (values: Array<Array<number | null>>, cells: number[], cols = 3, rows = 2): Heatmap => ({
    start: '2026-11-02T14:00:00Z',
    hours: values.length,
    grid: { cols, rows, bounds: [] },
    cells,
    values,
  })

  it('builds one upscaled frame per hour', () => {
    const { width, height, padCells, frames } = buildHeatmapFrames(
      grid([[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], [0, 1, 2, 3, 4, 5]),
      4,
    )
    expect(padCells).toBe(1)
    expect([width, height]).toEqual([(3 + 2) * 4, (2 + 2) * 4])
    expect(frames).toHaveLength(2)
    expect(frames[0]).toHaveLength(width * height * 4)
    expect(frames[0][3]).toBe(0) // padding corner is transparent
  })

  it('keeps a uniform field uniform inside the grid, premultiplied', () => {
    const { width, frames } = buildHeatmapFrames(grid([[20, 20, 20, 20, 20, 20]], [0, 1, 2, 3, 4, 5]), 4, 0)
    const [r, g, b, a] = colorForIndex(20)
    const expected = [r * (a / 255), g * (a / 255), b * (a / 255), a].map(Math.round)
    for (const [x, y] of [[0, 0], [5, 3], [11, 7]]) {
      pixel(frames[0], width, x, y).forEach((channel, i) => expect(channel).toBeCloseTo(expected[i], -0.5))
    }
  })

  it('fades to transparent outside the corridor and for missing values', () => {
    // Only the left column (cells 0 and 3) is in the corridor; hour 1 has no data at all.
    const { width, frames } = buildHeatmapFrames(grid([[40, 40], [null, null]], [0, 3]), 4, 0)
    expect(pixel(frames[0], width, 1, 1)[3]).toBeGreaterThan(150) // inside: strong No Travel
    expect(pixel(frames[0], width, 11, 1)[3]).toBe(0) // far right: transparent
    expect(frames[1].every((v) => v === 0)).toBe(true)
  })
})
