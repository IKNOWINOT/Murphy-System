
const q = new Map<string, number>();
function key(stateHash:string, action:number){ return `${stateHash}|${action}`; }
export function choose(stateHash:string, epsilon:number=0.1){
  if (Math.random()<epsilon) return Math.random()<0.5?0:1;
  const q0 = q.get(key(stateHash,0))||0, q1 = q.get(key(stateHash,1))||0;
  return q0>=q1?0:1;
}
export function update(trans:any[], lr:number=0.1, gamma:number=0.9){
  for (const t of trans){
    const [stateHash, action, reward, nextStateHash] = t;
    const bestNext = Math.max(q.get(key(nextStateHash,0))||0, q.get(key(nextStateHash,1))||0);
    const old = q.get(key(stateHash,action))||0;
    q.set(key(stateHash,action), old + lr*(reward + gamma*bestNext - old));
  }
}
