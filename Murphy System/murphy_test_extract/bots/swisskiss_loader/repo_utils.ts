const ALLOWED_LICENSES = new Set(['MIT','BSD','Apache','Apache-2.0','ISC','Unlicense','CC0']);

export type RepoInfo = {
  host: 'github' | 'gitlab' | 'unknown';
  owner?: string;
  repo?: string;
  url: string;
};

export function parseRepoUrl(url: string): RepoInfo {
  try {
    const u = new URL(url);
    if (u.hostname.toLowerCase().includes('github.com')) {
      const parts = u.pathname.replace(/^\//,'').split('/');
      return { host: 'github', owner: parts[0], repo: parts[1]?.replace(/\.git$/,'') || '', url };
    }
    if (u.hostname.toLowerCase().includes('gitlab.com')) {
      const parts = u.pathname.replace(/^\//,'').split('/');
      return { host: 'gitlab', owner: parts[0], repo: parts[1]?.replace(/\.git$/,'') || '', url };
    }
    return { host: 'unknown', url };
  } catch {
    return { host: 'unknown', url };
  }
}

async function fetchText(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'clockwork-swisskiss-loader' } });
    if (!res.ok) return null;
    return await res.text();
  } catch { return null; }
}

export async function analyzeReadme(repoUrl: string): Promise<string> {
  const info = parseRepoUrl(repoUrl);
  if (info.host === 'github' && info.owner && info.repo) {
    for (const fname of ['README.md','README','readme.md']) {
      const raw = `https://raw.githubusercontent.com/${info.owner}/${info.repo}/HEAD/${fname}`;
      const txt = await fetchText(raw);
      if (txt !== null) {
        const lines = txt.split(/\r?\n/).slice(0, 10);
        const joined = lines.join('\n');
        return joined || 'README present but empty.';
      }
    }
  }
  return 'No README found.';
}

export async function detectLicense(repoUrl: string): Promise<string> {
  const info = parseRepoUrl(repoUrl);
  if (info.host === 'github' && info.owner && info.repo) {
    for (const fname of ['LICENSE','LICENSE.txt','LICENSE.md','COPYING']) {
      const raw = `https://raw.githubusercontent.com/${info.owner}/${info.repo}/HEAD/${fname}`;
      const txt = await fetchText(raw);
      if (txt !== null) {
        for (const key of [...ALLOWED_LICENSES, 'GPL','LGPL','AGPL','MPL']) {
          if (txt.toLowerCase().includes(key.toLowerCase())) return key;
        }
        return 'UNKNOWN';
      }
    }
  }
  return 'MISSING';
}

export async function parseRequirements(repoUrl: string): Promise<{file:string,size:number}[]> {
  const info = parseRepoUrl(repoUrl);
  const out: {file:string,size:number}[] = [];
  if (info.host === 'github' && info.owner && info.repo) {
    const candidates = ['requirements.txt','pyproject.toml','package.json'];
    for (const fname of candidates) {
      const raw = `https://raw.githubusercontent.com/${info.owner}/${info.repo}/HEAD/${fname}`;
      const txt = await fetchText(raw);
      if (txt !== null) {
        out.push({ file: fname, size: new TextEncoder().encode(txt).length });
      }
    }
  }
  return out;
}

export async function detectLanguages(repoUrl: string): Promise<Record<string, number>> {
  const info = parseRepoUrl(repoUrl);
  if (info.host === 'github' && info.owner && info.repo) {
    const api = `https://api.github.com/repos/${info.owner}/${info.repo}/languages`;
    const txt = await fetchText(api);
    if (txt) {
      try { return JSON.parse(txt); } catch {}
    }
  }
  return {};
}

export async function riskScan(repoUrl: string, sampleFiles: string[] = ['README.md','package.json','requirements.txt']): Promise<{ issues: {file:string, pattern:string, pos:number}[], count: number }> {
  const risky = [
    /subprocess\.run/g, /os\.system/g, /eval\(/g, /exec\(/g,
    /requests\.(get|post)\(/g, /socket\./g, /paramiko\./g,
    /child_process\.exec/g, /fs\.unlink/g, /rm -rf/g
  ];
  const issues: {file:string, pattern:string, pos:number}[] = [];
  const info = parseRepoUrl(repoUrl);
  if (info.host === 'github' && info.owner && info.repo) {
    for (const fname of sampleFiles) {
      const raw = `https://raw.githubusercontent.com/${info.owner}/${info.repo}/HEAD/${fname}`;
      const txt = await fetchText(raw);
      if (txt) {
        for (const pat of risky) {
          let m: RegExpExecArray | null;
          while ((m = pat.exec(txt)) !== null) {
            issues.push({ file: fname, pattern: String(pat), pos: m.index });
          }
        }
      }
    }
  }
  return { issues, count: issues.length };
}

export function licenseOk(name: string): boolean {
  return ALLOWED_LICENSES.has(name);
}
