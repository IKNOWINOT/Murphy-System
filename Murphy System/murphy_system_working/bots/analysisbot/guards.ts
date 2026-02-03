// SQL safety & normalization utilities
const MUTATION = /\b(INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|BEGIN|COMMIT|ROLLBACK|VACUUM|ATTACH|DETACH|COPY|UNLOAD|LOAD|CALL|EXEC|XP_|PRAGMA)\b/i;

export function isReadOnly(sql:string): boolean {
  if (!sql) return false;
  const cleaned = stripComments(sql);
  if (cleaned.split(';').length > 1) return false;        // single statement only
  if (MUTATION.test(cleaned)) return false;               // block mutations
  return /^\s*WITH\b|^\s*SELECT\b/i.test(cleaned);     // must start with WITH or SELECT
}

export function enforceLimit(sql:string, max:number): string {
  const cleaned = stripComments(sql);
  if (/\bLIMIT\b/i.test(cleaned)) return sql;
  // naive LIMIT appender; dialect differences ignored for simplicity
  return `${sql.trim().replace(/;\s*$/,'')} LIMIT ${Math.max(1, max)};`;
}

export function stripComments(sql:string): string {
  return sql.replace(/--.*$/mg,'').replace(/\/\*[\s\S]*?\*\//g,'');
}
