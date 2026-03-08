import { describe, it, expect, vi, beforeEach } from 'vitest';
import { translateBlock } from '../internal/translate/router';

vi.mock('../internal/shim_model_proxy', () => ({
  callModel: vi.fn(),
}));

import { callModel } from '../internal/shim_model_proxy';
const mockCallModel = callModel as ReturnType<typeof vi.fn>;

beforeEach(() => { mockCallModel.mockReset(); });

describe('W3-04: Translation Router', () => {
  it('test_translate_with_model: returns model output for en→es', async () => {
    mockCallModel.mockResolvedValueOnce({ text: 'hola', confidence: 0.95, usage: { tokens_in: 5, tokens_out: 2, cost_usd: 0.0001 } });
    const result = await translateBlock('hello', 'en', 'es', {}, {}, []);
    expect(result.translated).toBe('hola');
    expect(result.translated_flag).toBe(true);
    expect(result.source_lang).toBe('en');
    expect(result.target_lang).toBe('es');
  });

  it('test_translate_model_unavailable_returns_original: model failure → original text, translated: false', async () => {
    mockCallModel.mockRejectedValueOnce(new Error('model unavailable'));
    const result = await translateBlock('hello', 'en', 'es', {}, {}, []);
    expect(result.translated).toBe('hello');
    expect(result.translated_flag).toBe(false);
    expect(result.reason).toBe('model_unavailable');
    expect(result.notes).toContain('model_unavailable');
  });

  it('test_translate_empty_model_response_uses_fallback', async () => {
    mockCallModel.mockResolvedValueOnce({ text: '', data: {}, result: {} });
    const result = await translateBlock('hello', 'en', 'fr', {}, {}, []);
    expect(result.translated).toBe('hello');
    expect(result.translated_flag).toBe(false);
  });

  it('test_translate_same_language_short_circuits', async () => {
    const result = await translateBlock('hello', 'en', 'en', {}, {}, []);
    expect(result.translated).toBe('hello');
    expect(result.quality).toBe(1.0);
    expect(result.notes).toContain('same-language');
    // callModel should NOT be called for same-language
    expect(mockCallModel).not.toHaveBeenCalled();
  });
});
