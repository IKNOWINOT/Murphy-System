
export default {
  ping: async (raw?:any)=>{
    const t = (raw?.task||'').toLowerCase();
    const kw=['observe','record','learn','automate','macro','adhd','attention','keystroke','mouse','window','google doc','golden path','osmosis','ingestion','playback','relay'];
    let s=0; for(const k of kw) if(t.includes(k)) s+=0.18;
    return { can_help: s>=0.25, confidence: Math.min(1,Math.max(0,s)), est_cost_usd: 0.003, must_have_inputs:[], archetype:'vallon_veritas' };
  }
}
