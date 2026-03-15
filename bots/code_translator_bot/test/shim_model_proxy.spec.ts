import { describe, it, expect, vi, beforeEach } from 'vitest';
import { callModel, callModelWithFallback, fallbackTranslate } from '../internal/shim_model_proxy';

describe('W3-05: Code Translator Shim', () => {
  const basePayload = {
    input: {
      params: {
        source_code: 'var x = 1 == 1;',
        src_lang: 'JavaScript',
        target_lang: 'TypeScript',
        filename: 'app.js',
        intent: 'translate',
      }
    }
  };

  it('test_code_translate_fallback: no real model → string-replace output, model_powered: false', async () => {
    const messages = [
      { role: 'system' as const, content: 'translate' },
      { role: 'user' as const, content: JSON.stringify(basePayload) },
    ];
    const resp = await callModel({ profile: 'mini', messages });
    expect(resp.model_powered).toBe(false);
    expect(resp.result.patches).toBeDefined();
    expect(resp.result.patches.length).toBeGreaterThan(0);
    // Should have applied string-replace transforms
    expect(resp.result.patches[0].after).toContain('let ');
    expect(resp.result.patches[0].after).toContain('===');
  });

  it('test_code_translate_with_model: real model → model output, model_powered: true', async () => {
    const mockRealModel = vi.fn().mockResolvedValueOnce({
      result: {
        patches: [{ before: 'var x = 1 == 1;', after: 'const x = 1 === 1;', diff: '', filename: 'app.ts', language: 'TypeScript' }],
        tests: [],
        explain: { summary: 'Model translation', key_points: [], risks: [] },
      },
      usage: { tokens_in: 100, tokens_out: 50, cost_usd: 0.005, model: 'turbo' },
    });
    const messages = [
      { role: 'system' as const, content: 'translate' },
      { role: 'user' as const, content: JSON.stringify(basePayload) },
    ];
    const resp = await callModelWithFallback({ profile: 'turbo', messages, callModelReal: mockRealModel });
    expect(resp.model_powered).toBe(true);
    expect(resp.result.model_powered).toBe(true);
    expect(resp.result.patches[0].after).toBe('const x = 1 === 1;');
    expect(mockRealModel).toHaveBeenCalledOnce();
  });

  it('test_code_translate_model_error_falls_back: real model throws → fallback used, model_powered: false', async () => {
    const mockRealModel = vi.fn().mockRejectedValueOnce(new Error('model unavailable'));
    const messages = [
      { role: 'system' as const, content: 'translate' },
      { role: 'user' as const, content: JSON.stringify(basePayload) },
    ];
    const resp = await callModelWithFallback({ profile: 'turbo', messages, callModelReal: mockRealModel });
    expect(resp.model_powered).toBe(false);
    expect(resp.result.patches.length).toBeGreaterThan(0);
    expect(resp.result.patches[0].after).toContain('let ');
  });

  it('test_fallback_translate_applies_var_to_let_and_double_to_triple_equals', () => {
    const result = fallbackTranslate({ source_code: 'var a = b == c;', src_lang: 'JavaScript', target_lang: 'TypeScript', filename: 'test.js', intent: 'translate' });
    expect(result.patches[0].after).toContain('let a');
    expect(result.patches[0].after).toContain('===');
    expect(result.model_powered).toBe(false);
  });
});
