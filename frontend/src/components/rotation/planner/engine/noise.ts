/**
 * 2D simplex noise (Stefan Gustavson's public-domain algorithm) with a fixed permutation, so the
 * demo landscape is identical on every device and every reload. Used only for the demo terrain.
 */
const GRAD = [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]];
const PERM = (() => {
  const p = Array.from({ length: 256 }, (_, i) => i);
  let s = 1337;
  for (let i = 255; i > 0; i--) { s = (s * 16807) % 2147483647; const j = s % (i + 1); [p[i], p[j]] = [p[j], p[i]]; }
  return Uint8Array.from([...p, ...p]);
})();
const F2 = 0.5 * (Math.sqrt(3) - 1), G2 = (3 - Math.sqrt(3)) / 6;

export function simplex2(xin: number, yin: number): number {
  const s = (xin + yin) * F2;
  const i = Math.floor(xin + s), j = Math.floor(yin + s);
  const t = (i + j) * G2;
  const x0 = xin - (i - t), y0 = yin - (j - t);
  const i1 = x0 > y0 ? 1 : 0, j1 = x0 > y0 ? 0 : 1;
  const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2, x2 = x0 - 1 + 2 * G2, y2 = y0 - 1 + 2 * G2;
  const ii = i & 255, jj = j & 255;
  let n = 0;
  for (const [x, y, g] of [[x0, y0, PERM[ii + PERM[jj]]], [x1, y1, PERM[ii + i1 + PERM[jj + j1]]], [x2, y2, PERM[ii + 1 + PERM[jj + 1]]]] as const) {
    const tt = 0.5 - x * x - y * y;
    if (tt > 0) { const gr = GRAD[g & 7]; n += tt ** 4 * (gr[0] * x + gr[1] * y); }
  }
  return 70 * n; // about -1..1
}

/** Fractal noise: several octaves of simplex. */
export function fbm(x: number, y: number, octaves = 5): number {
  let a = 0.5, f = 1, sum = 0, norm = 0;
  for (let o = 0; o < octaves; o++) { sum += a * simplex2(x * f, y * f); norm += a; a *= 0.5; f *= 2.03; }
  return sum / norm;
}

/** Deterministic pseudo-random sequence. */
export function rng(seed: number) { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
