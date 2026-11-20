// The Nous Girl as a platformer heroine, black and white only, after the Nous Research logo portrait: a chibi
// (the head is over half her height) with a long bob that curls out at the shoulders, headphones (a white band over
// the crown into a round black earpiece), two tall eyes, a striped top and a skirt. Each frame is drawn from a
// skeleton (hip, knees, shoulders, elbows), so run, jump, fall, land, skid, hurt and cheer are real poses; the head
// and hair are one fixed stamp in every pose. Coordinates face RIGHT; the game mirrors for left.
// K black, W white, '.' clear.

export const NG_W = 30, NG_H = 40 // 4 rows of headroom for the jump and cheer poses
// Head, hand-pixelled over the logo picture, drawn facing left like it; mirrored below.
// The white band is her headphones' band; it runs over the crown into the earpiece (round cup, thin rim, highlight).
const NG_HEAD_L = [
  '........KWWWKKK.......',
  '......KKKKKWWWKKK.....',
  '....KKKKKKKKKWWKKKK...',
  '...KKKKKKKKKKKWWKKKK..',
  '..KKWWKKKWWWKKWWKKWKK.',
  '..KWWKKKWWKWKKKWWKKKK.',
  '.KKKKKKKKKKKKKKKWWKKK.',
  '.KKKKKKWKKKKKKKWKKWKK.',
  '.KKKKKKKKKKKKKWKWWKWK.',
  '.KKKWWWWWWWWWKWKKKKWK.',
  '..KKWKKWWKKKWKKWKKWKK.',
  '...KWKKWWKKWWKKKWWKKK.',
  '...KWKKWWKKWWKKKKKKKK.',
  '...KWWWWWWWWWKKKKKKKK.',
  '....KWWKWWWWKKKKKKKKKK',
  '....KKWWWWWKKKKKKKKKKK',
  'K....KKWWWKKKKKKKKKWKK',
  'KWKKKKKWWKKKKKKKKKKKWK',
  '.KWWKKKKKKKKKKKKKKKKKK',
  '...KKK..KKKKK.....KKK.'
]
const NG_HEAD = NG_HEAD_L.map(r => [...r].reverse().join(''))
const NG_HW = 22, NG_NECK = 12 // head width; neck centre column in the mirrored head
const NG_LOWER = 15 // rows from here down are the hair ends, drawn behind the arms
// eyes in the facing-left head (mirrored when drawn): two tall 2x3 eyes, far eye cols 5-6 and near eye cols 9-10
// on rows 10-12, the near eye's lash flicking out at (11, 10) like the logo. Blink leaves a closed line on row 11;
// hurt puts an X on the near eye.
const ngM = ([x, y]) => [NG_HW - 1 - x, y]
const NG_EYE = {
  open: [[5, 10], [6, 10], [9, 10], [10, 10], [11, 10], [5, 12], [6, 12], [9, 12], [10, 12]].map(ngM),
  hurtK: [[9, 10], [11, 10], [10, 11], [9, 12], [11, 12]].map(ngM),
  hurtW: [[10, 10], [9, 11], [11, 11], [10, 12]].map(ngM)
}

// Striped sleeveless top (11 wide) and a short flared skirt (13 wide), anchored at the body centre.
// chibi build like the first sprite: the head is about 60% of her height
const NG_TOP = ['...KKWKK...', '.KKWWWWWKK.', '.KKKKKKKKK.', '.KWWWWWWWK.', '..KKKKKKK..']
const NG_SKIRT = {
  still: ['..KKKKKKKKK..', '.KKKKKKKKKKK.', '.KKKKKKKKKKK.'],
  sway: ['.KKKKKKKKKK..', 'KKKKKKKKKKK..', 'KKKKKKKKKKK..'],
  lift: ['..KKKKKKKKK..', '.KKKKKKKKKKK.', 'K.KKKKKKKK.K.']
}

function ngGrid() { return Array.from({ length: NG_H }, () => Array(NG_W).fill('.')) }
function ngPut(g, x, y, ch) { x = Math.round(x); y = Math.round(y); if (x >= 0 && y >= 0 && x < NG_W && y < NG_H) g[y][x] = ch }
function ngStamp(g, rows, x0, y0) { rows.forEach((r, j) => { for (let i = 0; i < r.length; i++) if (r[i] !== '.') ngPut(g, x0 + i, y0 + j, r[i]) }) }
function ngLine(g, x0, y0, x1, y1, ch) {
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1)
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1
  let e = dx + dy
  for (;;) { ngPut(g, x0, y0, ch); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx } if (e2 <= dx) { e += dx; y0 += sy } }
}
function ngThick(g, x0, y0, x1, y1, ch) { ngLine(g, x0, y0, x1, y1, ch); ngLine(g, x0 + 1, y0, x1 + 1, y1, ch) }
const ngRad = d => d * Math.PI / 180
// a limb from (x, y): first segment at angle a (degrees from straight down, + is forward), second bent by b
function ngLimb(x, y, a, b, l1, l2) {
  const kx = x + Math.sin(ngRad(a)) * l1, ky = y + Math.cos(ngRad(a)) * l1
  const c = a + b
  return { kx, ky, ex: kx + Math.sin(ngRad(c)) * l2, ey: ky + Math.cos(ngRad(c)) * l2 }
}
// black outline round every white pixel that touches the outside (in place)
function ngOutline(g) {
  const add = []
  for (let y = 0; y < NG_H; y++) for (let x = 0; x < NG_W; x++) {
    if (g[y][x] !== '.') continue
    if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([a, b]) => g[y + b] && g[y + b][x + a] === 'W')) add.push([x, y])
  }
  for (const [x, y] of add) g[y][x] = 'K'
}
// draw onto its own layer, outline it, then lay it over (so a limb keeps its outline in front of the body)
function ngLayer(g, draw, keep = () => true) {
  const l = ngGrid()
  draw(l)
  ngOutline(l)
  for (let y = 0; y < NG_H; y++) for (let x = 0; x < NG_W; x++) if (l[y][x] !== '.' && keep(x, y, l[y][x])) g[y][x] = l[y][x]
}

// pose: legs {f:[thigh, knee], b:[thigh, knee]}, arms {f:[upper, elbow], b:[...]}, lift (px raised, or null to
// plant the lowest foot), bob (body drop), lag (head drop), lean (upper body forward px), hair, skirt, blink, eyes
// arms: short black sleeves with one white hand pixel, close to the body (white or 2-px arms looked too big)
const NG_ARM = { thick: false, upper: 2, fore: 2, dx: 3, ink: 'K', hand: true }
function ngDraw(p) {
  const g = ngGrid()
  const cx = 14, THIGH = 3, SHIN = 4
  let hipY = NG_H - 2 - THIGH - SHIN + (p.bob || 0)
  const legs = ['b', 'f'].map(k => { const [t, kn] = p.legs[k]; return { k, ...ngLimb(cx + (k === 'f' ? 1 : -2), hipY, t, -kn, THIGH, SHIN) } })
  const dy = p.lift == null ? (NG_H - 2) - Math.max(...legs.map(l => l.ey)) : -p.lift
  hipY += dy
  for (const l of legs) { l.ky += dy; l.ey += dy }
  const lean = p.lean || 0
  const skirtY = hipY - 2
  const topY = skirtY - NG_TOP.length
  const shY = topY + 1
  const hx = cx - NG_NECK + lean, hy = topY - NG_HEAD.length + 1 + (p.lag || 0)
  const arm = k => { const sx = cx + lean + (k === 'f' ? NG_ARM.dx : -NG_ARM.dx); const [u, e] = p.arms[k]; return { sx, ...ngLimb(sx, shY + 1, u, e, NG_ARM.upper, NG_ARM.fore) } }
  // an arm: upper arm and forearm with a small round fist
  // arms: thin and short (size from the pose's 'arm' style, default 1 px wide), no separate hand
  const drawArm = (l, a) => {
    const line = NG_ARM.thick ? ngThick : ngLine, ink = NG_ARM.ink || 'W'
    line(l, a.sx, shY + 1, a.kx, a.ky, ink); line(l, a.kx, a.ky, a.ex, a.ey, ink)
    if (NG_ARM.hand) ngPut(l, a.ex, a.ey + 1, 'W')
  }
  const shoe = (gg, l, front) => { const x = Math.round(l.ex), y = Math.round(l.ey) + 1; for (let i = -1; i <= (front ? 2 : 1); i++) ngPut(gg, x + i, y, 'K'); ngPut(gg, x, y - 1, 'K'); ngPut(gg, x + 1, y - 1, 'K') }
  // the hair is static: the back ends sit behind the body and arms, the rest of the head in front
  const lower = NG_HEAD.slice(NG_LOWER)
  const back = lower.map(r => r.slice(0, NG_NECK - 1))
  const front = lower.map(r => '.'.repeat(NG_NECK - 1) + r.slice(NG_NECK - 1))
  ngStamp(g, back, hx, hy + NG_LOWER)
  // back arm and back leg
  const ab = arm('b')
  ngLayer(g, l => drawArm(l, ab))
  const lb = legs[0]
  ngLayer(g, l => { ngThick(l, cx - 2, hipY, lb.kx, lb.ky, 'W'); ngThick(l, lb.kx, lb.ky, lb.ex, lb.ey, 'W') })
  shoe(g, lb, false)
  // skirt, top
  ngStamp(g, NG_SKIRT[p.skirt || 'still'], cx - 6, skirtY)
  ngStamp(g, NG_TOP, cx - 5 + lean, topY)
  // front leg over the skirt (its outline stops at the hem)
  const lf = legs[1]
  ngLayer(g, l => { ngThick(l, cx + 1, hipY + 1, lf.kx, lf.ky, 'W'); ngThick(l, lf.kx, lf.ky, lf.ex, lf.ey, 'W') }, (x, y, ch) => !(ch === 'K' && y < hipY + 1))
  shoe(g, lf, true)
  // head and eye states
  ngStamp(g, NG_HEAD.slice(0, NG_LOWER), hx, hy)
  ngStamp(g, front, hx, hy + NG_LOWER)
  // blink: only the lash lines stay; hurt: an X over the near eye
  if (p.blink) for (const [x, y] of NG_EYE.open) ngPut(g, hx + x, hy + y, 'W')
  if (p.eyes === 'x') { for (const [x, y] of NG_EYE.hurtW) ngPut(g, hx + x, hy + y, 'W'); for (const [x, y] of NG_EYE.hurtK) ngPut(g, hx + x, hy + y, 'K') }
  // front arm last, outlined over the top
  const af = arm('f')
  ngLayer(g, l => drawArm(l, af))
  ngOutline(g)
  return g.map(r => r.join(''))
}

// ---- the animation set
const NG_POSES = (() => {
  const P = {}
  const still = { f: [4, 2], b: [-4, 2] }
  P.idle = [0, 0, 1, 1].map(b => ({ legs: still, arms: { f: [8, 6], b: [-8, 6] }, bob: b, lag: b, hair: 'still' }))
  P.blink = { ...P.idle[0], blink: true }
  P.run = []
  for (let i = 0; i < 8; i++) {
    const t = i / 8 * Math.PI * 2
    const leg = ph => [38 * Math.sin(ph), 12 + 62 * Math.max(0, Math.cos(ph)) * (0.6 + 0.4 * Math.max(0, Math.sin(ph) + 0.4))]
    P.run.push({
      legs: { f: leg(t), b: leg(t + Math.PI) },
      // arms pump opposite the legs, elbows bent about 90 degrees, fists coming up to chest height in front
      // arms hang by her sides and swing a little, opposite the legs (arms jutting forward or out behind the
      // hip did not look natural)
      arms: { f: [-18 * Math.sin(t), 12], b: [10 * Math.sin(t), 8] },
      lean: 1, skirt: i % 4 < 2 ? 'sway' : 'still'
    })
  }
  P.jumpUp = { legs: { f: [62, 95], b: [-10, 35] }, arms: { f: [160, 10], b: [-50, 30] }, lift: 3, hair: 'still', skirt: 'still' }
  P.jumpTop = { legs: { f: [35, 60], b: [5, 45] }, arms: { f: [115, 20], b: [-95, 20] }, lift: 3, hair: 'lift', skirt: 'lift' }
  P.fall = [
    { legs: { f: [18, 22], b: [-12, 40] }, arms: { f: [125, 10], b: [-120, 10] }, lift: 2, hair: 'lift', skirt: 'lift', lag: -1 },
    { legs: { f: [8, 34], b: [-4, 24] }, arms: { f: [135, 10], b: [-130, 10] }, lift: 2, hair: 'lift', skirt: 'lift', lag: -1 }
  ]
  P.land = { legs: { f: [38, 78], b: [-34, 70] }, arms: { f: [40, 30], b: [-40, 30] }, bob: 2, lag: 3, hair: 'still', lean: 1 }
  P.skid = { legs: { f: [42, 4], b: [-8, 45] }, arms: { f: [70, 30], b: [-30, 60] }, lean: -1, hair: 'lift', skirt: 'sway' }
  P.hurt = { legs: { f: [25, 30], b: [-25, 30] }, arms: { f: [150, 20], b: [-150, 20] }, lift: 1, lean: -1, eyes: 'x', hair: 'lift', skirt: 'lift' }
  P.cheer = [
    { legs: still, arms: { f: [170, 0], b: [-170, 0] }, hair: 'still' },
    { legs: { f: [10, 30], b: [-10, 30] }, arms: { f: [165, 0], b: [-165, 0] }, lift: 2, hair: 'lift', skirt: 'lift' }
  ]
  return P
})()

export function ngFrames() {
  const F = {}
  for (const [k, v] of Object.entries(NG_POSES)) F[k] = Array.isArray(v) ? v.map(ngDraw) : ngDraw(v)
  return F
}
