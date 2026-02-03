
export function buildPlan(template:any, domain:string){
  // simple deterministic hierarchy from requirements
  const epics = (template.requirements||[]).map((r:string,i:number)=> ({
    id:`E${i+1}`, title:`Epic: ${r}`, level:'epic', rationale:`Delivers ${r}`, children:[]
  }));
  const stories = [];
  let tCounter=1;
  for (const e of epics){
    const caps = [{title:`Capability: ${e.title.split(': ')[1]} core`},{title:`Capability: ${e.title.split(': ')[1]} edge`}];
    for (const [ci,c] of caps.entries()){
      const capId = `${e.id}-C${ci+1}`;
      const capNode:any = { id:capId, title:c.title, level:'capability', children:[] };
      for (let k=0;k<3;k++){
        const stId = `${capId}-S${k+1}`;
        const stNode:any = { id:stId, title:`Story ${k+1}`, level:'story', children:[] };
        for (let m=0;m<2;m++){
          const taskId = `${stId}-T${m+1}`;
          stNode.children.push({ id:taskId, title:`Task ${tCounter++}`, level:'task', acceptance_tests:[`Test ${taskId}`], children:[] });
        }
        capNode.children.push(stNode);
      }
      e.children.push(capNode);
    }
    stories.push(...e.children||[]);
  }
  const plan = { tree: epics, dependencies: [], acceptance_tests: [{id:'A1', text:'KPI baselines defined'}] };
  return plan;
}
