
import { topFrequentQueries } from '../db/queries';
export async function promoteIfEligible(db:D1Database, goldenPaths:any, windowHours=24){
  const hot = await topFrequentQueries(db, windowHours);
  for (const h of hot){
    const key = { task_type:'librarian_bot', query:h.query, tags: h.tags_json };
    // A simple curated spec storing top doc ids will be attached by caller
    // goldenPaths.recordPath(db, { task_type:'librarian_bot', key, success:true, confidence:0.9, spec:{ curated:true } });
  }
}
