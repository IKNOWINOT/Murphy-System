// src/clockwork/bots/commissioning_bot/internal/adapters/point_map.ts
// Smarter BAS point-list mapping: synonyms + configurable column map
export type ColumnMap = { asset?:string; name?:string; type?:string; unit?:string };

const SYNONYMS: Record<string, string[]> = {
  asset: ['Equipment','Asset','Device','Equipment Name','Equip'],
  name:  ['Point Name','Name','Signal','Point'],
  type:  ['Point Type','Type','Signal Type','I/O Type'],
  unit:  ['Unit','Units','Eng Units','EU']
};

export function bestColumn(columns:string[], target:'asset'|'name'|'type'|'unit'): string|undefined {
  const lower = columns.map(c=>c.toLowerCase());
  for (const syn of SYNONYMS[target]) {
    const idx = lower.indexOf(syn.toLowerCase());
    if (idx>=0) return columns[idx];
  }
  return undefined;
}

export function mapRows(rows:Array<Record<string,any>>, map?:ColumnMap) {
  if (!rows.length) return [];
  const columns = Object.keys(rows[0]);
  const cmap: ColumnMap = {
    asset: map?.asset || bestColumn(columns,'asset'),
    name:  map?.name  || bestColumn(columns,'name'),
    type:  map?.type  || bestColumn(columns,'type'),
    unit:  map?.unit  || bestColumn(columns,'unit')
  };
  return rows.map(r => ({
    asset: cmap.asset ? r[cmap.asset] : undefined,
    name:  cmap.name  ? r[cmap.name]  : undefined,
    type:  cmap.type  ? r[cmap.type]  : undefined,
    unit:  cmap.unit  ? r[cmap.unit]  : undefined
  }));
}
