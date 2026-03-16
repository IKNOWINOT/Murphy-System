
export function hydrate(seed:number, shape:number[]){
  let s = seed>>>0;
  function rand(){ s = (1664525*s + 1013904223)>>>0; return (s&0xffffffff)/4294967296; }
  const total = shape.reduce((a,b)=>a*b,1);
  const arr = new Array(total).fill(0).map(()=>rand());
  return { data: arr, shape };
}
export function fold(arr:number[]){ const n=arr.length; const mean=arr.reduce((a,b)=>a+b,0)/Math.max(1,n); const v=arr.reduce((a,b)=>a+(b-mean)*(b-mean),0)/Math.max(1,n-1); const sd=Math.sqrt(v); const min=Math.min(...arr), max=Math.max(...arr); const topk=arr.map((v,i)=>[i,v]).sort((a,b)=>b[1]-a[1]).slice(0,10); return { stats:{min,max,mean,sd}, topk }; }
