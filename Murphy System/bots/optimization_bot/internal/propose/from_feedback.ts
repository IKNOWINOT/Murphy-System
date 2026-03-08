export async function proposeFromFeedback(_db:any, _ctx:any){
  try {
    if (!_db) return [];
    // Query feedback action clusters
    const result = await _db.prepare(
      `SELECT bot, area, COUNT(*) as count, AVG(score) as avg_score
       FROM feedback_actions
       GROUP BY bot, area
       HAVING count >= 3 AND avg_score < 0`
    ).all();
    const rows: any[] = result?.results || [];
    const proposals: any[] = [];
    for (const row of rows){
      const confidence = Math.min(0.9, 0.5 + (-row.avg_score) * 0.2 + Math.min(row.count, 20) * 0.01);
      proposals.push({
        target_bot: row.bot,
        area: row.area,
        proposal: `Review and improve ${row.area} in ${row.bot}: ${row.count} negative feedback entries (avg score ${row.avg_score.toFixed(2)})`,
        confidence: +confidence.toFixed(3),
        gated: true,
      });
    }
    return proposals;
  } catch {
    return [];
  }
}