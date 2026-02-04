
export function ttcQuestions(goal:string){
  return [
    { axis:'who', prompt:'Who is the target audience/reader?', options:['End users','Developers','Support','Stakeholders'] },
    { axis:'what', prompt:'What domain/style should we follow?', options:['Product UI','API docs','Legal','Marketing','General'] },
    { axis:'when', prompt:'When is this due or launched?', options:['ASAP','1 week','1 month','Quarter'] },
    { axis:'where', prompt:'Where/Locale preferences (e.g., ja-JP, en-GB)?', options:['en-US','ja-JP','de-DE','fr-FR'] },
    { axis:'how', prompt:'How should we handle glossary/no-translate and tone?', options:['Strict glossary','Do-not-translate for brand','Neutral tone','Formal tone'] },
    { axis:'why', prompt:'Why are we translating/transpiling (goal/metric)?', options:['Comprehension','Conversion','Dev productivity','Localization readiness'] }
  ].map((q,i)=>({...q,id:`${q.axis}_${i+1}`}));
}
