import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ocrImage } from '../internal/model_proxy/ocr';
import { asrAudio } from '../internal/model_proxy/asr';
import { captionImage } from '../internal/model_proxy/caption';

vi.mock('../internal/shim_model_proxy', () => ({
  callModel: vi.fn(),
}));

import { callModel } from '../internal/shim_model_proxy';
const mockCallModel = callModel as ReturnType<typeof vi.fn>;

const dummyCtx = {};
const dummyBytes = new Uint8Array([1, 2, 3]);

beforeEach(() => { mockCallModel.mockReset(); });

describe('W3-01: OCR model proxy', () => {
  it('test_ocr_with_model_available: returns extracted text and confidence > 0', async () => {
    mockCallModel.mockResolvedValueOnce({ text: 'Hello World', confidence: 0.92, usage: { tokens_in: 10, tokens_out: 5, cost_usd: 0.001 } });
    const result = await ocrImage(dummyCtx, dummyBytes);
    expect(result.text).toBe('Hello World');
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.stub).toBeUndefined();
  });

  it('test_ocr_with_model_unavailable: returns fallback string and confidence = 0', async () => {
    mockCallModel.mockRejectedValueOnce(new Error('model unavailable'));
    const result = await ocrImage(dummyCtx, dummyBytes);
    expect(result.text).toBe('[ocr unavailable]');
    expect(result.confidence).toBe(0);
    expect(result.stub).toBe(true);
  });

  it('test_ocr_empty_response_uses_fallback', async () => {
    mockCallModel.mockResolvedValueOnce({ text: '', data: {}, result: {} });
    const result = await ocrImage(dummyCtx, dummyBytes);
    expect(result.text).toBe('[ocr unavailable]');
    expect(result.confidence).toBe(0);
  });
});

describe('W3-02: ASR model proxy', () => {
  it('test_asr_with_model_available: returns transcription and confidence > 0', async () => {
    mockCallModel.mockResolvedValueOnce({ text: 'the quick brown fox', confidence: 0.88, usage: { tokens_in: 8, tokens_out: 4, cost_usd: 0.0005 } });
    const result = await asrAudio(dummyCtx, dummyBytes);
    expect(result.text).toBe('the quick brown fox');
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.stub).toBeUndefined();
  });

  it('test_asr_with_model_unavailable: returns fallback string and confidence = 0', async () => {
    mockCallModel.mockRejectedValueOnce(new Error('timeout'));
    const result = await asrAudio(dummyCtx, dummyBytes);
    expect(result.text).toBe('[asr unavailable]');
    expect(result.confidence).toBe(0);
    expect(result.stub).toBe(true);
  });

  it('test_asr_empty_response_uses_fallback', async () => {
    mockCallModel.mockResolvedValueOnce({ text: '', data: {}, result: {} });
    const result = await asrAudio(dummyCtx, dummyBytes);
    expect(result.text).toBe('[asr unavailable]');
    expect(result.confidence).toBe(0);
  });
});

describe('W3-03: Caption model proxy', () => {
  it('test_caption_with_model_available: returns model caption ≠ hardcoded stub', async () => {
    mockCallModel.mockResolvedValueOnce({ result: { caption: 'A dog running in a park' }, confidence: 0.9, usage: { tokens_in: 12, tokens_out: 8, cost_usd: 0.002 } });
    const result = await captionImage(dummyCtx, dummyBytes, 'normal');
    expect(result.caption).toBe('A dog running in a park');
    expect(result.caption).not.toContain('stub');
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.stub).toBeUndefined();
  });

  it('test_caption_with_model_unavailable: returns fallback and confidence = 0', async () => {
    mockCallModel.mockRejectedValueOnce(new Error('model unavailable'));
    const result = await captionImage(dummyCtx, dummyBytes, 'short');
    expect(result.caption).toBe('A photo.');
    expect(result.confidence).toBe(0);
    expect(result.stub).toBe(true);
  });

  it('test_caption_normal_verbosity_fallback', async () => {
    mockCallModel.mockRejectedValueOnce(new Error('timeout'));
    const result = await captionImage(dummyCtx, dummyBytes, 'normal');
    expect(result.caption).toBe('An image.');
    expect(result.confidence).toBe(0);
  });

  it('test_caption_result_text_field_fallback', async () => {
    mockCallModel.mockResolvedValueOnce({ result: { text: 'A scenic mountain view' }, confidence: 0.8, usage: { tokens_in: 5, tokens_out: 5, cost_usd: 0.001 } });
    const result = await captionImage(dummyCtx, dummyBytes, 'verbose');
    expect(result.caption).toBe('A scenic mountain view');
    expect(result.confidence).toBeGreaterThan(0);
  });
});
