
export function translateComments(code:string, src:string, tgt:string, glossary:any){
  const lines = code.split(/\r?\n/); const out:string[]=[];
  for (const line of lines){
    const m = line.match(/^(.*?)(\/\/|#)(.*)$/);
    if (m){ const pre=m[1], cmt=m[3]; out.push(pre + (m[2]) + ' ' + cmt); } else out.push(line);
  }
  return out.join('\n');
}
