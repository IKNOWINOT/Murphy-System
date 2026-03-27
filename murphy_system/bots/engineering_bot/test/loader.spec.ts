import { describe, it, expect, vi } from 'vitest';
import { loadJSON } from '../internal/data/loader';

function makeDB(data: Record<string, string | null>) {
  return {
    prepare(sql: string) {
      const api = {
        args: [] as any[],
        bind: (...args: any[]) => { api.args = args; return api; },
        first: async () => {
          const key = api.args[0];
          if (/FROM engineering_data/.test(sql)) {
            const val = data[key];
            return val !== undefined ? { value: val } : null;
          }
          return null;
        },
      };
      return api;
    }
  };
}

function makeKV(data: Record<string, string | null>) {
  return {
    async get(key: string) { return data[key] ?? null; },
  };
}

describe('W3-10: Engineering Bot Data Loader', () => {
  it('test_load_json_from_d1: D1 has data → returned correctly', async () => {
    const db = makeDB({ 'config.json': JSON.stringify({ threshold: 42, mode: 'strict' }) });
    const result = await loadJSON('config.json', { db });
    expect(result).toEqual({ threshold: 42, mode: 'strict' });
  });

  it('test_load_json_d1_miss_kv_hit: D1 empty, KV has data → KV data returned', async () => {
    const db = makeDB({});
    const kv = makeKV({ 'settings.json': JSON.stringify({ debug: true }) });
    const result = await loadJSON('settings.json', { db, kv });
    expect(result).toEqual({ debug: true });
  });

  it('test_load_json_all_miss: both empty → {} returned', async () => {
    const db = makeDB({});
    const kv = makeKV({});
    const result = await loadJSON('missing.json', { db, kv });
    expect(result).toEqual({});
  });

  it('test_load_json_no_ctx: no ctx at all → {} returned', async () => {
    const result = await loadJSON('any.json');
    expect(result).toEqual({});
  });

  it('test_load_json_malformed_d1: D1 returns invalid JSON → {} returned, no crash', async () => {
    const db = makeDB({ 'bad.json': 'not valid json {{{' });
    const warnSpy = vi.fn();
    const result = await loadJSON('bad.json', { db, logger: { warn: warnSpy } });
    expect(result).toEqual({});
    expect(warnSpy).toHaveBeenCalled();
  });

  it('test_load_json_malformed_kv: KV returns invalid JSON → {} returned, no crash', async () => {
    const db = makeDB({});
    const kv = makeKV({ 'bad.json': '{{invalid}}' });
    const warnSpy = vi.fn();
    const result = await loadJSON('bad.json', { db, kv, logger: { warn: warnSpy } });
    expect(result).toEqual({});
    expect(warnSpy).toHaveBeenCalled();
  });

  it('test_load_json_db_throws: D1 throws → falls back to KV', async () => {
    const brokenDB = {
      prepare(_sql: string) {
        return {
          bind: (..._args: any[]) => this,
          first: async () => { throw new Error('DB connection failed'); }
        };
      }
    };
    const kv = makeKV({ 'fallback.json': JSON.stringify({ fallback: true }) });
    const result = await loadJSON('fallback.json', { db: brokenDB, kv });
    expect(result).toEqual({ fallback: true });
  });

  it('test_load_json_d1_null_value: D1 returns null value → falls to KV', async () => {
    const db = makeDB({ 'key': null });
    const kv = makeKV({ 'key': JSON.stringify({ from: 'kv' }) });
    const result = await loadJSON('key', { db, kv });
    expect(result).toEqual({ from: 'kv' });
  });
});
