
export function avgColor(pixels:number[][][]){
  // pixels: [H][W][3]
  let r=0,g=0,b=0,c=0;
  for (const row of pixels){ for (const p of row){ r+=p[0]||0; g+=p[1]||0; b+=p[2]||0; c++; } }
  if (!c) return {r:0,g:0,b:0};
  return { r: Math.round(r/c), g: Math.round(g/c), b: Math.round(b/c) };
}
export function brightness({r,g,b}:{r:number,g:number,b:number}){
  return Math.round((r*299 + g*587 + b*114)/1000);
}
export function colorBins(pixels:number[][][], bins:number=5){
  const h=new Array(bins).fill(0);
  for(const row of pixels){ for(const [r,g,b] of row){
    const y=Math.round((r+g+b)/3);
    const i=Math.max(0,Math.min(bins-1, Math.floor(y/(256/bins)))); h[i]++;
  }} return h;
}
