// Minimal GLTF-ish data structure or fallback SVG polyline for 3D line
export function makeModel3DSpec(data:any, title:string='Model'): { type:'gltf'|'svg', spec:any } {
  const X = data?.X || []; const Y = data?.Y || []; const Z = data?.Z || [];
  if (Array.isArray(X) && X.length && X.length===Y.length && Y.length===Z.length) {
    return {
      type: 'gltf',
      spec: {
        asset: { version: '2.0' },
        extras: { title },
        nodes: [{ name:'path3d', extras:{ polyline:{ X, Y, Z } } }]
      }
    };
  }
  // fallback simple SVG
  const points = (data?.points || []).map((p:any)=>`${p[0]},${p[1]}`).join(' ');
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='800' height='600'><polyline points='${points}' fill='none' stroke='#333'/></svg>`;
  return { type:'svg', spec: svg };
}
