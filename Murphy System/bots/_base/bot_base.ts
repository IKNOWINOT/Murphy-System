// Stub for _base/bot_base used by bots that wrap their run function with withBotBase
export type Ctx = {
  userId?: string;
  tier?: string;
  kv?: any;
  db?: any;
  env?: any;
  emit?: (e: string, d: any) => any;
  logger?: { warn?: Function; error?: Function };
  runId?: string;
  startTs?: number;
};

export function withBotBase(_opts: any, fn: Function): Function {
  // In production, this wraps the bot function with quota/budget checks.
  // As a stub, just return the function directly.
  return fn;
}
