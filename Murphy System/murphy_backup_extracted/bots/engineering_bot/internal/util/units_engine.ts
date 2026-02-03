
// Base-dimension unit engine (subset). Extend as needed.
type Dim = [number,number,number,number,number,number,number]; // M,L,T,I,Theta,N,J (SI base + extras)
const U: Record<string,{k:number, d:Dim}> = {
  // Scalars
  '': {k:1,d:[0,0,0,0,0,0,0]},
  // Length
  'm':{k:1,d:[0,1,0,0,0,0,0]}, 'mm':{k:1e-3,d:[0,1,0,0,0,0,0]}, 'cm':{k:1e-2,d:[0,1,0,0,0,0,0]}, 'in':{k:0.0254,d:[0,1,0,0,0,0,0]}, 'ft':{k:0.3048,d:[0,1,0,0,0,0,0]},
  // Mass
  'kg':{k:1,d:[1,0,0,0,0,0,0]}, 'g':{k:1e-3,d:[1,0,0,0,0,0,0]}, 'lb':{k:0.45359237,d:[1,0,0,0,0,0,0]},
  // Time
  's':{k:1,d:[0,0,1,0,0,0,0]},
  // Temperature (use K offset)
  'K':{k:1,d:[0,0,0,0,1,0,0]},
  // Force
  'N':{k:1,d:[1,1,-2,0,0,0,0]},
  // Pressure
  'Pa':{k:1,d:[1,-1,-2,0,0,0,0]}, 'bar':{k:1e5,d:[1,-1,-2,0,0,0,0]},
  // Energy
  'J':{k:1,d:[1,2,-2,0,0,0,0]},
  // Power
  'W':{k:1,d:[1,2,-3,0,0,0,0]}
};

function addDim(a:Dim,b:Dim,sign=1):Dim{ const r:Dim=[0,0,0,0,0,0,0]; for(let i=0;i<7;i++) r[i]=a[i]+sign*b[i]; return r; }
function sameDim(a:Dim,b:Dim){ for(let i=0;i<7;i++) if(a[i]!==b[i]) return false; return true; }

export function convert(val:number, from:string, to:string){
  const F=U[from]; const T=U[to]; if(!F||!T) throw new Error('unit not found'); if(!sameDim(F.d,T.d)) throw new Error('incompatible units');
  return val*F.k/T.k;
}
