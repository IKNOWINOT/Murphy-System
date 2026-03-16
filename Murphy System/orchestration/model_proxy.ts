type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(_args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }): Promise<any> {
  return { data: { confidence: 0.5 } };
}
