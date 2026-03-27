
export function jsToPy(code:string){
  const lines=code.split(/\r?\n/); const py:string[]=[]; let ind=0;
  for (const raw of lines){
    const line=raw.trim().replace(/;$/,''); 
    if (line.startsWith('function ')){
      const header=line.substring(9).split('{')[0].trim(); const [name,args]= header.includes('(')? [header.split('(')[0], header.slice(header.indexOf('(')+1,-1)] : [header,''];
      py.push(' '.repeat(ind)+`def ${name}(${args}):`); ind+=4;
    } else if (line=='}'){ ind=Math.max(0,ind-4); }
    else if (line.endsWith('{')){ py.push(' '.repeat(ind)+line.slice(0,-1)+':'); ind+=4; }
    else if (line.startsWith('console.log')){ py.push(' '.repeat(ind)+'print'+line.substring(11)); }
    else { py.push(' '.repeat(ind)+line); }
  }
  return py.join('\n');
}
