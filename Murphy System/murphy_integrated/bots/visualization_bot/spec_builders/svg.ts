// Technical SVG builder for simple CAD scope parts list
type Part = { id:string; x?:number; y?:number; w?:number; h?:number; label?:string };
type Scope = { parts?: Part[]; explode?: number };

export function makeTechSVG(scope: Scope, title:string='Exploded View'): string {
  const parts = Array.isArray(scope?.parts) ? scope.parts : [];
  const explode = typeof scope?.explode === 'number' ? scope.explode : 20;
  const width = 800, height = 600;
  const rows = Math.max(1, Math.ceil(Math.sqrt(Math.max(1, parts.length))));
  const cols = rows;

  function esc(s:string){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  const items:string[] = [];
  parts.forEach((p, i) => {
    const col = i % cols; const row = Math.floor(i/cols);
    const px = (p.x ?? 50 + col* (150+explode)) + (row*5);
    const py = (p.y ?? 60 + row* (120+explode)) + (col*3);
    const w = p.w ?? 120; const h = p.h ?? 80;
    const label = p.label || p.id;
    items.push(`<rect x="${px}" y="${py}" width="${w}" height="${h}" rx="8" ry="8" fill="#eee" stroke="#333"/>`);
    items.push(`<line x1="${px+w/2}" y1="${py+h}" x2="${px+w/2}" y2="${py+h+20}" stroke="#555"/>`);
    items.push(`<text x="${px+w/2}" y="${py+h+35}" font-size="12" text-anchor="middle" fill="#222">${esc(label)}</text>`);
    // dimension labels
    items.push(`<text x="${px+w+10}" y="${py+12}" font-size="10" fill="#666">${w}×${h}</text>`);
  });

  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n  <title>${esc(title)}</title>\n  ${items.join('\n  ')}\n</svg>`;
}
