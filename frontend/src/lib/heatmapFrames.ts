import type { Heatmap } from '../api/types'
import { RISK_LEVELS } from './risk'

// Opacity per risk band: the band colour identifies the level exactly (matching the legend and the
// checkpoints); opacity rises within the band. Low stays a faint tint so calm corridors don't wash out the
// map, while gradients within it remain visible.
const BAND_ALPHA: ReadonlyArray<[number, number]> = [
  [0.08, 0.28], // Low
  [0.48, 0.6], // Moderate
  [0.6, 0.7], // High
  [0.7, 0.8], // Severe
  [0.85, 0.85], // No Travel
]

/** Straight-alpha RGBA for a risk index ×10 (0–40). */
export function colorForIndex(value: number): [number, number, number, number] {
  const index = Math.min(Math.max(value / 10, 0), 4)
  const band = Math.min(Math.floor(index), 4)
  const [r, g, b] = RISK_LEVELS[band].rgb
  const [from, to] = BAND_ALPHA[band]
  const alpha = from + (to - from) * (index - band)
  return [r, g, b, Math.round(alpha * 255)]
}

export interface HeatmapFrames {
  width: number
  height: number
  /** Transparent cells added around the grid so the corridor fades out instead of ending at the image edge. */
  padCells: number
  /** One premultiplied-alpha RGBA image per forecast hour, row 0 = north. */
  frames: Uint8ClampedArray[]
}

/**
 * Turns the coarse forecast grid (one value per ~10–30 mi cell) into smooth images, once per heatmap:
 * bilinear upscaling plus a light box blur, in premultiplied alpha so the corridor edge fades out cleanly.
 * Cell centres keep their position, so the images still line up with the grid bounds.
 */
export function buildHeatmapFrames(heatmap: Heatmap, scale = 4, padCells = 1): HeatmapFrames {
  const cols = heatmap.grid.cols + 2 * padCells
  const rows = heatmap.grid.rows + 2 * padCells
  const width = cols * scale
  const height = rows * scale
  // Grid cell index → index in the padded grid.
  const padded = heatmap.cells.map((cell) => {
    const row = Math.floor(cell / heatmap.grid.cols) + padCells
    const col = (cell % heatmap.grid.cols) + padCells
    return row * cols + col
  })
  const frames = heatmap.values.map((hourValues) => {
    const grid = new Float32Array(cols * rows * 4)
    padded.forEach((cell, i) => {
      const value = hourValues[i]
      if (value === null || value === undefined) return
      const [r, g, b, a] = colorForIndex(value)
      const alpha = a / 255
      grid.set([r * alpha, g * alpha, b * alpha, a], cell * 4)
    })
    const upscaled = upscaleBilinear(grid, cols, rows, scale)
    return Uint8ClampedArray.from(boxBlur(upscaled, width, height, Math.max(1, Math.floor(scale / 2))))
  })
  return { width, height, padCells, frames }
}

function upscaleBilinear(src: Float32Array, cols: number, rows: number, scale: number): Float32Array {
  const width = cols * scale
  const height = rows * scale
  const out = new Float32Array(width * height * 4)
  for (let y = 0; y < height; y++) {
    const sy = Math.min(Math.max((y + 0.5) / scale - 0.5, 0), rows - 1)
    const y0 = Math.floor(sy)
    const y1 = Math.min(y0 + 1, rows - 1)
    const fy = sy - y0
    for (let x = 0; x < width; x++) {
      const sx = Math.min(Math.max((x + 0.5) / scale - 0.5, 0), cols - 1)
      const x0 = Math.floor(sx)
      const x1 = Math.min(x0 + 1, cols - 1)
      const fx = sx - x0
      const o = (y * width + x) * 4
      for (let c = 0; c < 4; c++) {
        const top = src[(y0 * cols + x0) * 4 + c] * (1 - fx) + src[(y0 * cols + x1) * 4 + c] * fx
        const bottom = src[(y1 * cols + x0) * 4 + c] * (1 - fx) + src[(y1 * cols + x1) * 4 + c] * fx
        out[o + c] = top * (1 - fy) + bottom * fy
      }
    }
  }
  return out
}

/** Separable box blur (sliding window, clamp-to-edge). */
function boxBlur(src: Float32Array, width: number, height: number, radius: number): Float32Array {
  const pass = (input: Float32Array, length: number, lines: number, index: (line: number, i: number) => number) => {
    const output = new Float32Array(input.length)
    const span = 2 * radius + 1
    for (let line = 0; line < lines; line++) {
      for (let c = 0; c < 4; c++) {
        const at = (i: number) => input[index(line, Math.min(Math.max(i, 0), length - 1)) * 4 + c]
        let sum = 0
        for (let i = -radius; i <= radius; i++) sum += at(i)
        for (let i = 0; i < length; i++) {
          output[index(line, i) * 4 + c] = sum / span
          sum += at(i + radius + 1) - at(i - radius)
        }
      }
    }
    return output
  }
  const horizontal = pass(src, width, height, (row, x) => row * width + x)
  return pass(horizontal, height, width, (col, y) => y * width + col)
}
