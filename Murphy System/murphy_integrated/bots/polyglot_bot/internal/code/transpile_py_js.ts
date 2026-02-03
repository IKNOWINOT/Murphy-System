
function _indent(n:number){ return '  '.repeat(Math.max(0,n)); }
export function pyToJs(code:string){
  const lines=code.split(/\r?\n/); const js:string[]=[];
  const indent:number[]=[0];
  for (const line of lines){
    const stripped=line.trim(); const ind=line.length - stripped.length;
    while(ind < indent[indent.length-1]){ indent.pop(); js.push(_indent(indent.length-1)+'}'); }
    if (stripped.startsWith('def ')){ const header=stripped.substring(4).replace(/:\s*$/,''); js.push(_indent(indent.length-1)+`function ${header} {`); indent.push(ind+4); }
    else if (stripped.startsWith('print(')){ js.push(_indent(indent.length-1)+'console.log'+stripped.substring(5)+';'); }
    else if (stripped.startsWith('return ')){ js.push(_indent(indent.length-1)+stripped+';'); }
    else if (stripped.endsWith(':')){ js.push(_indent(indent.length-1)+stripped.slice(0,-1)+' {'); indent.push(ind+4); }
    else { js.push(_indent(indent.length-1)+stripped); }
  }
  while(indent.length>1){ indent.pop(); js.push(_indent(indent.length-1)+'}'); }
  return js.join('\n');
}
