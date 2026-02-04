
function parseCSVLine(line:string){
  const out:string[]=[]; let cur='', inq=false;
  for (let i=0;i<line.length;i++){
    const c=line[i];
    if (c==='"'){ if (inq && line[i+1]==='"'){ cur+='"'; i++; } else inq=!inq; }
    else if (c===',' && !inq){ out.push(cur); cur=''; }
    else cur+=c;
  }
  out.push(cur); return out;
}
function sanitizeCell(cell:string){
  if (!cell) return cell;
  if (/^[=+\-@]/.test(cell)) return `'${cell}`;
  return cell;
}
export function parseCSV(text:string, strict:boolean){
  const lines=text.split(/\r?\n/).filter(l=>l.length>0);
  if (!lines.length) return { data:{rows:[]}, issues:[] };
  const header=parseCSVLine(lines[0]).map(h=>h.trim());
  const rows:any[]=[]; const issues:any[]=[];
  for (let i=1;i<lines.length;i++){
    const cols=parseCSVLine(lines[i]);
    if (cols.length!==header.length) issues.push({level:'warn', line:i+1, message:'Column count mismatch'});
    const row:any={};
    for (let j=0;j<header.length;j++){ row[header[j]] = sanitizeCell(cols[j]||''); }
    rows.push(row);
  }
  return { data:{rows}, issues };
}
