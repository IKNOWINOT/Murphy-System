
export function thompsonSample(arms:{arm_id:string, alpha:number, beta:number}[]){
  let best = arms[0].arm_id, bestS = -1;
  for (const a of arms){
    const s = betaSample(a.alpha, a.beta);
    if (s>bestS){ bestS=s; best=a.arm_id; }
  }
  return best;
}

// Proper Beta distribution sampling using the gamma-ratio method (Jöhnk / Marsaglia-Tsang).
// For α,β >= 1: Gamma sampling via Marsaglia-Tsang; return x/(x+y) where x~Gamma(α,1), y~Gamma(β,1).
// For α < 1 or β < 1: Jöhnk's algorithm.
export function betaSample(alpha: number, beta: number): number {
  if (alpha <= 0 || beta <= 0) return 0.5; // guard
  if (alpha < 1 || beta < 1) {
    return betaSampleJohnk(alpha, beta);
  }
  const x = gammaSample(alpha);
  const y = gammaSample(beta);
  const s = x + y;
  if (s === 0) return 0.5;
  return x / s;
}

// Marsaglia & Tsang's method for Gamma(α, 1) sampling, α >= 1.
function gammaSample(alpha: number): number {
  const d = alpha - 1/3;
  const c = 1 / Math.sqrt(9 * d);
  while (true) {
    let x: number, v: number;
    do {
      x = randn();
      v = 1 + c * x;
    } while (v <= 0);
    v = v * v * v;
    const u = Math.random();
    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

// Jöhnk's algorithm for Beta(α, β) when α < 1 or β < 1.
function betaSampleJohnk(alpha: number, beta: number): number {
  while (true) {
    const u = Math.pow(Math.random(), 1 / alpha);
    const v = Math.pow(Math.random(), 1 / beta);
    if (u + v <= 1) {
      const s = u + v;
      if (s === 0) continue;
      return u / s;
    }
  }
}

// Box-Muller standard normal sample.
function randn(): number {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// Kept for comparison / testing purposes.
export function betaSampleCrude(alpha: number, beta: number): number {
  const n = 6;
  let s = 0;
  for (let i = 0; i < n; i++) { s += Math.random(); }
  const u = s / n;
  return Math.pow(u, 1/alpha) * Math.pow(1-u, 1/beta);
}
