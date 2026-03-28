type Msg={role:'system'|'user'|'assistant',content:string};
function tok(s:string){return(s||'').toLowerCase().replace(/[^a-z0-9\s]/g,' ').split(/\s+/).filter(Boolean)}
function vec(t:string){const m:any={};for(const w of tok(t))m[w]=(m[w]||0)+1;return m}
function cos(a:any,b:any){let d=0,na=0,nb=0;const keys=new Set([...Object.keys(a),...Object.keys(b)]);for(const k of keys){const va=a[k]||0,vb=b[k]||0;d+=va*vb;na+=va*va;nb+=vb*vb}if(!na||!nb)return 0;return d/Math.sqrt(na*nb)}
class UF{p:number[];r:number[];constructor(n:number){this.p=[...Array(n).keys()];this.r=Array(n).fill(0)}f(x:number){return this.p[x]===x?x:(this.p[x]=this.f(this.p[x]))}u(a:number,b:number){a=this.f(a);b=this.f(b);if(a===b)return;if(this.r[a]<this.r[b])this.p[a]=b;else if(this.r[a]>this.r[b])this.p[b]=a;else{this.p[b]=a;this.r[a]++}}}
export async function callModel(args:{profile:'mini'|'turbo',messages:Msg[],json?:boolean,maxTokens?:number}){
  const user=args.messages.find(m=>m.role==='user')?.content||'{}';let p:any={};try{p=JSON.parse(user)}catch{}const par=p?.input?.params||{};const threshold: number=par.threshold??0.92;
  const texts:Record<string,string>={...(par.texts||{})};for(const a of(p?.input?.attachments||[])){if(a?.id!=null&&typeof a.text==='string')texts[String(a.id)]=a.text}
  const ids=Object.keys(texts);const n=ids.length;const vecs=ids.map(id=>vec(texts[id]));const uf=new UF(n);const scores:any[]=[];
  for(let i=0;i<n;i++){for(let j=i+1;j<n;j++){const s=cos(vecs[i],vecs[j]);scores.push({id1:ids[i],id2:ids[j],score:s});if(s>threshold)uf.u(i,j)}}
  const groups:any={};for(let i=0;i<n;i++){const r=uf.f(i);(groups[r] ||= []).push(ids[i])}
  const clusters=Object.values(groups).filter((g:any)=>g.length>1).map((m:any)=>{const canonical_id=m.slice().sort()[0];return{canonical_id,members:m,scores:scores.filter(s=>m.includes(s.id1)&&m.includes(s.id2))}});
  const merges:any[]=[];const mapping:any={};for(const c of clusters){const keep=c.canonical_id;for(const m of c.members){if(m===keep)continue;const sc=c.scores.find((s:any)=> (s.id1===keep&&s.id2===m)||(s.id1===m&&s.id2===keep))?.score??threshold;merges.push({keep,drop:m,score:sc,strategy:'append'});mapping[m]=keep}}
  return { result:{clusters,merges,mapping}, usage:{tokens_in:150,tokens_out:200,cost_usd:args.profile==='turbo'?0.008:0.002,model:args.profile} }
}