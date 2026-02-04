export async function buildEmailTemplates(model_proxy:any, tone:string, campaign:any, count:number=3) {
  const prompt = [
    { role: 'system', content: 'You are a world-class outbound marketer. Return STRICT JSON: { templates: [{subject, preview, html, text}] }' },
    { role: 'user', content: JSON.stringify({ tone, campaign, count }) }
  ];
  const resp = await model_proxy.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 1200 });
  return resp?.data?.templates || [];
}
export async function buildLandingSpec(model_proxy:any, tone:string, campaign:any) {
  const prompt = [
    { role: 'system', content: 'Return STRICT JSON: { spec: {...}, html: "<!doctype html>..."} for a high-converting landing page with hero, benefits, social proof, CTA. No external CSS.' },
    { role: 'user', content: JSON.stringify({ tone, campaign }) }
  ];
  const resp = await model_proxy.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 1800 });
  return { spec: resp?.data?.spec || {}, html: resp?.data?.html || '<!doctype html><html><body><h1>Landing</h1></body></html>' };
}
export async function buildAdCopy(model_proxy:any, tone:string, campaign:any, platforms:string[]=['google','facebook','linkedin']) {
  const prompt = [
    { role: 'system', content: 'Return STRICT JSON: { ads: [{ platform, headline, body, url }] } with 3 variants per platform. Keep to platform limits.' },
    { role: 'user', content: JSON.stringify({ tone, campaign, platforms }) }
  ];
  const resp = await model_proxy.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 1200 });
  return resp?.data?.ads || [];
}
