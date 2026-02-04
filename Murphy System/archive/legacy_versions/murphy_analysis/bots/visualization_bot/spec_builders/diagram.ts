// Mermaid-like sequence/flow DSL generator from a simple description
export function makeDiagramSpec(task:string, annotations:any): { type:'mermaid', dsl:string } {
  // Very simple template; expects annotations.nodes/edges optionally
  const nodes:string[] = (annotations?.nodes || ['A','B','C']).map((n:any)=>String(n));
  const edges:any[] = (annotations?.edges || [{from:'A',to:'B'},{from:'B',to:'C'}]);
  const lines:string[] = ['flowchart LR'];
  for (const n of nodes) lines.push(`${n}[${n}]`);
  for (const e of edges) lines.push(`${e.from} --> ${e.to}`);
  return { type:'mermaid', dsl: lines.join('\n') };
}
