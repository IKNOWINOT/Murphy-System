
export async function proposeActionsViaModelProxy(recurring:any[], ctx:any){
  if (!recurring.length) return [];
  return recurring.slice(0,3).map(r => ({
    type: "prompt_patch",
    target_bot: r.key.bot,
    category: r.key.category,
    action_json: { patch: "Adjust schema or prompt hints where mismatch occurs." },
    confidence: 0.6
  }));
}
