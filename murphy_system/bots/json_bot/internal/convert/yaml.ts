export function parseYaml(text:string, strict:boolean){
  const issues:any[]=[]; const obj:any={};
  const lines = text.split(/\r?\n/);
  let ok=true;
  for (let i=0;i<lines.length;i++){
    const line = lines[i];
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const m = line.match(/^([^:#]+):\s*(.*)$/);
    if (!m){ ok=false; issues.push({level:'error', line:i+1, message:'Only simple key: value lines allowed (safe YAML subset)'}); continue; }
    const key=m[1].trim(); const val=m[2].trim();
    obj[key]= val;
  }
  if (strict && !ok) throw new Error('YAML parse error (safe subset)');
  return { data: obj, issues };
}