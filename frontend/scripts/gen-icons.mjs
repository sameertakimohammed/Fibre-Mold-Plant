// One-shot generator for the PWA icons (192 + 512). Produces plain colored
// PNGs: dark brand background with an amber rounded square and a white "G".
// Run: node scripts/gen-icons.mjs   (output → public/icons/)
//
// Hand-rolled PNG encoder (truecolor + alpha, zlib via node:zlib) so we add no
// image dependency. Kept here only as a build-time asset generator.
import { writeFileSync, mkdirSync } from 'node:fs'
import { deflateSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = join(__dirname, '..', 'public', 'icons')
mkdirSync(OUT, { recursive: true })

const BG = [0x0d, 0x10, 0x14]      // --bg
const AMBER = [0xf5, 0xa6, 0x23]   // --amber
const DARKTEXT = [0x1a, 0x12, 0x05] // dark glyph on amber (matches nav active)

function crc32(buf) {
  let c = ~0
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i]
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1))
  }
  return ~c >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0)
  const t = Buffer.from(type, 'ascii')
  const body = Buffer.concat([t, data])
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(body), 0)
  return Buffer.concat([len, body, crc])
}

function encodePNG(width, height, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8     // bit depth
  ihdr[9] = 6     // color type RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0
  // raw scanlines with filter byte 0
  const stride = width * 4
  const raw = Buffer.alloc((stride + 1) * height)
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, y * stride + stride)
  }
  const idat = deflateSync(raw, { level: 9 })
  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', idat),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

function makeIcon(size) {
  const rgba = Buffer.alloc(size * size * 4)
  const set = (x, y, [r, g, b], a = 255) => {
    if (x < 0 || y < 0 || x >= size || y >= size) return
    const i = (y * size + x) * 4
    rgba[i] = r; rgba[i + 1] = g; rgba[i + 2] = b; rgba[i + 3] = a
  }
  // background
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) set(x, y, BG)

  // amber rounded square panel
  const pad = Math.round(size * 0.10)
  const rad = Math.round(size * 0.20)
  const inRounded = (x, y) => {
    if (x < pad || y < pad || x >= size - pad || y >= size - pad) return false
    const dx = Math.min(x - pad, (size - 1 - pad) - x)
    const dy = Math.min(y - pad, (size - 1 - pad) - y)
    if (dx >= rad || dy >= rad) return true
    const cx = dx < rad ? pad + rad : (size - 1 - pad) - rad
    const cy = dy < rad ? pad + rad : (size - 1 - pad) - rad
    return Math.hypot(x - cx, y - cy) <= rad
  }
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (inRounded(x, y)) set(x, y, AMBER)

  // "G": an open ring with a horizontal bar + stub on the right.
  const cx = size / 2, cy = size / 2
  const rOut = size * 0.235, rIn = size * 0.14
  const thick = rOut - rIn
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - cx, dy = y - cy
      const d = Math.hypot(dx, dy)
      const ang = Math.atan2(dy, dx) // -PI..PI
      // ring, but leave a mouth opening on the right (roughly -35°..35°)
      const onRing = d >= rIn && d <= rOut
      const mouth = ang > -0.6 && ang < 0.45 && d > (cx - x > 0 ? 0 : 0) // gate by angle
      if (onRing && !(mouth && dx > 0)) set(x, y, DARKTEXT)
      // inner horizontal bar of the G (from center to right inner edge)
      if (dy > -thick * 0.5 && dy < thick * 0.55 && dx > -size * 0.01 && d <= rOut && d >= rIn * 0.2 && dx > 0) {
        set(x, y, DARKTEXT)
      }
    }
  }

  return encodePNG(size, size, rgba)
}

for (const size of [192, 512]) {
  const png = makeIcon(size)
  writeFileSync(join(OUT, `icon-${size}.png`), png)
  console.log(`wrote icons/icon-${size}.png (${png.length} bytes)`)
}
