import { describe, it, expect } from 'vitest';
import { betaSample, betaSampleCrude, thompsonSample } from '../internal/bandit/thompson';

describe('W3-09: Beta Distribution Sampling', () => {
  it('test_beta_sample_mean: 10000 samples from Beta(2,5) → mean ≈ 0.286 ± 0.03', () => {
    const N = 10000;
    let sum = 0;
    for (let i = 0; i < N; i++) sum += betaSample(2, 5);
    const mean = sum / N;
    const expectedMean = 2 / (2 + 5); // ≈ 0.2857
    expect(mean).toBeGreaterThan(expectedMean - 0.03);
    expect(mean).toBeLessThan(expectedMean + 0.03);
  });

  it('test_beta_sample_variance: variance ≈ α*β / ((α+β)²*(α+β+1)) for Beta(2,5)', () => {
    const alpha = 2, beta = 5;
    const N = 10000;
    const samples: number[] = [];
    for (let i = 0; i < N; i++) samples.push(betaSample(alpha, beta));
    const mean = samples.reduce((a, b) => a + b, 0) / N;
    const variance = samples.reduce((a, b) => a + (b - mean) ** 2, 0) / N;
    const expectedVariance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1));
    // Allow ±50% tolerance for variance estimate
    expect(variance).toBeGreaterThan(expectedVariance * 0.5);
    expect(variance).toBeLessThan(expectedVariance * 1.5);
  });

  it('test_beta_sample_edge_cases: Beta(1,1) → uniform [0,1]', () => {
    const N = 1000;
    const samples: number[] = [];
    for (let i = 0; i < N; i++) samples.push(betaSample(1, 1));
    // Mean of Beta(1,1) = 0.5, should be close
    const mean = samples.reduce((a, b) => a + b, 0) / N;
    expect(mean).toBeGreaterThan(0.4);
    expect(mean).toBeLessThan(0.6);
    // All samples should be in [0, 1]
    expect(samples.every(s => s >= 0 && s <= 1)).toBe(true);
  });

  it('test_beta_sample_edge_cases: Beta(0.5, 0.5) → does not crash', () => {
    expect(() => {
      for (let i = 0; i < 100; i++) betaSample(0.5, 0.5);
    }).not.toThrow();
    const sample = betaSample(0.5, 0.5);
    expect(sample).toBeGreaterThanOrEqual(0);
    expect(sample).toBeLessThanOrEqual(1);
  });

  it('test_beta_sample_alpha_lt_1: Beta(0.3, 2) → mean ≈ 0.3/2.3 ≈ 0.13', () => {
    const alpha = 0.3, beta = 2;
    const N = 5000;
    let sum = 0;
    for (let i = 0; i < N; i++) sum += betaSample(alpha, beta);
    const mean = sum / N;
    const expectedMean = alpha / (alpha + beta);
    expect(mean).toBeGreaterThan(expectedMean - 0.04);
    expect(mean).toBeLessThan(expectedMean + 0.04);
  });

  it('betaSampleCrude still works for comparison', () => {
    const sample = betaSampleCrude(2, 5);
    expect(sample).toBeGreaterThanOrEqual(0);
    expect(sample).toBeLessThanOrEqual(1);
  });

  it('thompsonSample selects from available arms', () => {
    const arms = [
      { arm_id: 'A', alpha: 1, beta: 9 },   // low success rate
      { arm_id: 'B', alpha: 9, beta: 1 },   // high success rate
    ];
    // Run many times; B should win more often
    const counts: Record<string, number> = { A: 0, B: 0 };
    for (let i = 0; i < 1000; i++) {
      const winner = thompsonSample(arms);
      counts[winner]++;
    }
    // B should win the vast majority of the time
    expect(counts['B']).toBeGreaterThan(counts['A']);
  });
});
