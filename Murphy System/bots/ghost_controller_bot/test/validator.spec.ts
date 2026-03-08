import { describe, it, expect, vi, beforeEach } from 'vitest';
import { validateMicroTasks } from '../internal/microtasks/validator';

const sampleMicroTasks = [
  { id: 'mt_s1', goal: 'Perform focus_app', preconditions: [], steps: [{ id: 's1', action: 'focus_app', args: { app: 'Chrome' } }], success: { type: 'window', selector: 'Chrome', timeout_s: 10 } },
];

const sampleMicroTasksNeedingCapability = [
  { id: 'mt_s1', goal: 'analyze documents', preconditions: [], steps: [{ id: 's1', action: 'analyze', args: {} }], success: { type: 'noop', timeout_s: 5 } },
];

describe('W3-07: Ghost Controller Validator', () => {
  it('dry-run always passes (existing behavior preserved)', async () => {
    const results = await validateMicroTasks(sampleMicroTasks, true);
    expect(results).toHaveLength(1);
    expect(results[0].passed).toBe(true);
    expect(results[0].details).toBe('dry-run pass');
  });

  it('test_validate_live_bot_available: healthy ping → valid: true', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 200 });
    const ctx = { fetch: mockFetch as any, targetBot: 'my-bot' };
    const results = await validateMicroTasks(sampleMicroTasks, false, ctx);
    expect(results[0].passed).toBe(true);
    expect(results[0].errors).toHaveLength(0);
    expect(mockFetch).toHaveBeenCalledWith('http://my-bot/ping', expect.any(Object));
  });

  it('test_validate_live_bot_unavailable: fetch throws → valid: false, errors: [bot unreachable]', async () => {
    const mockFetch = vi.fn().mockRejectedValueOnce(new Error('connection timeout'));
    const ctx = { fetch: mockFetch as any, targetBot: 'unreachable-bot' };
    const results = await validateMicroTasks(sampleMicroTasks, false, ctx);
    expect(results[0].passed).toBe(false);
    expect(results[0].errors).toContain('bot unreachable');
  });

  it('test_validate_live_bot_unhealthy_status: ping returns non-ok → valid: false', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 503 });
    const ctx = { fetch: mockFetch as any, targetBot: 'sick-bot' };
    const results = await validateMicroTasks(sampleMicroTasks, false, ctx);
    expect(results[0].passed).toBe(false);
    expect(results[0].errors).toContain('bot unreachable');
  });

  it('test_validate_live_capability_mismatch: bot capabilities missing required intent → valid: false', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 200 });
    const ctx = {
      fetch: mockFetch as any,
      targetBot: 'limited-bot',
      botCapabilities: ['translate', 'summarize'], // does NOT have 'analyze'
    };
    const results = await validateMicroTasks(sampleMicroTasksNeedingCapability, false, ctx);
    expect(results[0].passed).toBe(false);
    expect(results[0].errors?.some(e => e.includes('capability mismatch'))).toBe(true);
  });

  it('test_validate_live_capability_match: bot has required intent → passes capability check', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 200 });
    const ctx = {
      fetch: mockFetch as any,
      targetBot: 'capable-bot',
      botCapabilities: ['analyze', 'classify', 'triage'],
    };
    const results = await validateMicroTasks(sampleMicroTasksNeedingCapability, false, ctx);
    expect(results[0].passed).toBe(true);
    expect(results[0].errors).toHaveLength(0);
  });

  it('test_validate_live_no_target_bot: no bot specified → skips ping, checks schema only', async () => {
    const results = await validateMicroTasks(sampleMicroTasks, false, {});
    // No target bot, no capabilities to check, step has action → should pass
    expect(results[0].passed).toBe(true);
  });

  it('test_validate_live_missing_action_in_step: invalid step schema → valid: false', async () => {
    const badMicrotasks = [
      { id: 'mt_bad', goal: 'do something', preconditions: [], steps: [{ id: 's1', args: {} }], success: {} },
    ];
    const results = await validateMicroTasks(badMicrotasks, false, {});
    expect(results[0].passed).toBe(false);
    expect(results[0].errors?.some(e => e.includes("step missing 'action'"))).toBe(true);
  });
});
