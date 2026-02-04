
export function parseTextBlob(text:string){
  const result:any={}; const issues:any[]=[];
  const lines=text.trim().split(/\r?\n/);
  for (let i=0;i<lines.length;i++){
    const line=lines[i]; if (!line.trim()) continue;
    if (line.includes(':')){ const [k,...rest]=line.split(':'); result[k.trim()]=rest.join(':').trim(); }
    else { result[`line_${i}`]=line.trim(); }
  }
  return { data: result, issues };
}
