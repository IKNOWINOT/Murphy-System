type Msg = { role: 'system'|'user'|'assistant'; content: string };

export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }): Promise<any> {
  // Shim: in production this is replaced by a real Workers AI / model proxy call.
  return { text: '', data: {}, result: {} };
}
