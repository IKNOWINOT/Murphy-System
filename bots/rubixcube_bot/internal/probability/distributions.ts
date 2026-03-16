
import { phi, invPhi } from './erf';

export function normalCDF(x:number, mu=0, sigma=1){ return phi((x-mu)/Math.max(1e-9,sigma)); }
export function normalPDF(x:number, mu=0, sigma=1){ const z=(x-mu)/Math.max(1e-9,sigma); return Math.exp(-0.5*z*z)/(Math.max(1e-9,sigma)*Math.sqrt(2*Math.PI)); }
export function normalQuantile(p:number, mu=0, sigma=1){ return mu + sigma*invPhi(p); }

export function expCDF(x:number, lambda=1){ if(x<0) return 0; return 1-Math.exp(-lambda*x); }
export function expPDF(x:number, lambda=1){ return x<0?0: lambda*Math.exp(-lambda*x); }
export function expQuantile(p:number, lambda=1){ return -Math.log(1-p)/lambda; }

export function binomPMF(k:number, n:number, p:number){ function logChoose(n:number,k:number){ if(k<0||k>n) return -1e9; let s=0; for(let i=1;i<=k;i++){ s += Math.log((n+1-i)/i); } return s; } const lp = k*Math.log(p) + (n-k)*Math.log(1-p) + logChoose(n,k); return Math.exp(lp); }
export function binomCDF(k:number, n:number, p:number){ let s=0; for(let i=0;i<=Math.floor(k);i++){ s+=binomPMF(i,n,p); } return Math.min(1, s); }

export function poissonPMF(k:number,lambda:number){ if(k<0) return 0; let s=Math.exp(-lambda); for(let i=1;i<=k;i++){ s*=lambda/i; } return s; }
export function poissonCDF(k:number,lambda:number){ let s=0; for(let i=0;i<=Math.floor(k);i++){ s+=poissonPMF(i,lambda); } return Math.min(1,s); }
