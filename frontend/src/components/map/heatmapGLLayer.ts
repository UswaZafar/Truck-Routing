import {
  type CustomLayerInterface,
  type CustomRenderMethodInput,
  type Map as MapLibreMap,
  MercatorCoordinate,
} from 'maplibre-gl'

import type { HeatmapFrames } from '../../lib/heatmapFrames'

const VERTEX_SHADER = `
attribute vec2 a_pos;
attribute vec2 a_uv;
uniform mat4 u_matrix;
varying vec2 v_uv;
void main() {
  v_uv = a_uv;
  gl_Position = u_matrix * vec4(a_pos, 0.0, 1.0);
}`

const FRAGMENT_SHADER = `
precision mediump float;
uniform sampler2D u_texture;
uniform float u_opacity;
varying vec2 v_uv;
void main() {
  gl_FragColor = texture2D(u_texture, v_uv) * u_opacity;
}`

type GL = WebGLRenderingContext | WebGL2RenderingContext

/**
 * Draws the corridor heatmap as one textured quad. Every forecast hour is uploaded as its own texture when
 * the layer is added; switching hours just binds another texture and repaints. Unlike changing a source or a
 * paint property, that never triggers MapLibre's style update / label placement, so the slider stays smooth.
 */
export class HeatmapGLLayer implements CustomLayerInterface {
  readonly type = 'custom' as const
  readonly renderingMode = '2d' as const
  private map: MapLibreMap | null = null
  private program: WebGLProgram | null = null
  private buffer: WebGLBuffer | null = null
  private textures: WebGLTexture[] = []
  private frame = 0
  private readonly id_: string

  constructor(
    id: string,
    private readonly images: HeatmapFrames,
    /** Grid corners [lng, lat]: top-left, top-right, bottom-right, bottom-left. */
    private readonly corners: Array<[number, number]>,
    private readonly grid: { cols: number; rows: number },
    private readonly opacity = 0.9,
  ) {
    this.id_ = id
  }

  get id() {
    return this.id_
  }

  setFrame(index: number) {
    if (index === this.frame) return
    this.frame = index
    this.map?.triggerRepaint()
  }

  onAdd(map: MapLibreMap, gl: GL) {
    this.map = map
    this.program = createProgram(gl, VERTEX_SHADER, FRAGMENT_SHADER)

    // The grid is a rectangle in Mercator space; widen it by the frames' transparent padding cells.
    const [tl, , br] = this.corners.map((corner) => MercatorCoordinate.fromLngLat(corner))
    const padX = ((br.x - tl.x) / this.grid.cols) * this.images.padCells
    const padY = ((br.y - tl.y) / this.grid.rows) * this.images.padCells
    const [west, north, east, south] = [tl.x - padX, tl.y - padY, br.x + padX, br.y + padY]
    // Triangle strip TL, BL, TR, BR — x, y (mercator 0..1), u, v
    const vertices = new Float32Array([west, north, 0, 0, west, south, 0, 1, east, north, 1, 0, east, south, 1, 1])
    this.buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer)
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW)

    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false) // frames are already premultiplied
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1)
    const { width, height } = this.images
    this.textures = this.images.frames.map((pixels) => {
      const texture = gl.createTexture()!
      gl.bindTexture(gl.TEXTURE_2D, texture)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
      return texture
    })
  }

  render(gl: GL, options: CustomRenderMethodInput) {
    const program = this.program
    if (!program || !this.textures.length) return
    // Don't let our attribute setup leak into a vertex array object MapLibre left bound.
    if ('bindVertexArray' in gl) gl.bindVertexArray(null)

    gl.useProgram(program)
    gl.uniformMatrix4fv(gl.getUniformLocation(program, 'u_matrix'), false, options.defaultProjectionData.mainMatrix)
    gl.uniform1f(gl.getUniformLocation(program, 'u_opacity'), this.opacity)
    gl.uniform1i(gl.getUniformLocation(program, 'u_texture'), 0)
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, this.textures[this.frame])

    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer)
    const position = gl.getAttribLocation(program, 'a_pos')
    const uv = gl.getAttribLocation(program, 'a_uv')
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 16, 0)
    gl.enableVertexAttribArray(uv)
    gl.vertexAttribPointer(uv, 2, gl.FLOAT, false, 16, 8)

    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
  }

  onRemove(_map: MapLibreMap, gl: GL) {
    this.textures.forEach((texture) => gl.deleteTexture(texture))
    gl.deleteBuffer(this.buffer)
    gl.deleteProgram(this.program)
    this.textures = []
    this.map = null
  }
}

function createProgram(gl: GL, vertexSource: string, fragmentSource: string): WebGLProgram {
  const compile = (type: number, source: string) => {
    const shader = gl.createShader(type)!
    gl.shaderSource(shader, source)
    gl.compileShader(shader)
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? 'shader error')
    return shader
  }
  const program = gl.createProgram()!
  gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource))
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource))
  gl.linkProgram(program)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? 'link error')
  return program
}
