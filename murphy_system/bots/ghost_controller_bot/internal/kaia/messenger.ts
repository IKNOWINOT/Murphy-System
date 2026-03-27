
export function dailyQuestions(capture_ref:string){
  const mk=(id:string,axis:any,prompt:string,opts:string[]=[])=>( {id, capture_ref, axis, prompt, options:opts, allow_multi:true} );
  return [
    mk('q_who_1','who','What is your job title?'),
    mk('q_who_2','who','Who are you doing this for?', ['self','manager','client','team','other']),
    mk('q_who_3','who','Who benefits from this?', ['self','team','org','customer','other']),
    mk('q_what_1','what','What is the task that is being done?'),
    mk('q_what_2','what','What are the ways it can be done?'),
    mk('q_what_3','what','What are the benefits from this?'),
    mk('q_when_1','when','When do you use this?'),
    mk('q_when_2','when','When is it not ideal?'),
    mk('q_where_1','where','Where is it applicable?'),
    mk('q_where_2','where','Where does the information stay?'),
    mk('q_where_3','where','Where does the information go?'),
    mk('q_how_1','how','How will you capture this? (the capture itself)'),
    mk('q_why_1','why','Why do you do it?'),
    mk('q_why_2','why','Why is it done this way specifically?')
  ];
}
export function suggestionsFromHistory(answers:any[], weeks:number=2){
  const arr:string[]=[];
  if(weeks>=2) arr.push('Consider batching similar tasks and scheduling a focused block.');
  if(answers.find(a=>a.id==='q_where_2')) arr.push('Create a canonical storage location and link automations to it.');
  return arr;
}
