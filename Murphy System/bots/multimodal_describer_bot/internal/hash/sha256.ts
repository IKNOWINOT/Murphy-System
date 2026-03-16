
export async function sha256Base64(s:string){
  const enc=new TextEncoder().encode(s);
  const d=await crypto.subtle.digest('SHA-256', enc);
  return btoa(String.fromCharCode(...new Uint8Array(d)));
}
