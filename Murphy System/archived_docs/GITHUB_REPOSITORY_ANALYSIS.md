# GitHub Repository to Module Capability Analysis

## Executive Summary

**The current Murphy System implementation DOES NOT have GitHub repository-to-module conversion functionality.**

However, the **original Murphy Runtime System** (in `murphy_test_extract/`) contains a **SwissKiss Loader Bot** that can:
- Fetch and analyze GitHub repositories
- Extract README, license, requirements, and language information
- Perform risk scans
- Generate module metadata (module.yaml)
- Stage modules for review

---

## Current System Status

### What's NOT Available in Current Implementation

The current Murphy System (`murphy_backend_complete.py`) **does NOT include**:
- ❌ GitHub repository fetching
- ❌ Repository analysis (README, license, requirements)
- ❌ Module YAML generation from repos
- ❌ Risk scanning of code
- ❌ Language detection
- ❌ Dependency extraction

### What IS Available

The current system has:
- ✅ Artifact Generation System (generates artifacts from documents, not repos)
- ✅ Database Integration (stores artifacts, not repo modules)
- ✅ Monitoring, Shadow Agents, Cooperative Swarm
- ✅ 42+ API endpoints (none for GitHub repos)

---

## Original System Capability (SwissKiss Loader)

### Location
`/workspace/murphy_test_extract/bots/swisskiss_loader/`

### Capabilities

The **SwissKiss Manual Loader Bot v2.0** (TypeScript) can:

1. **Repository Analysis**
   - Fetch README files from GitHub/GitLab
   - Detect licenses (MIT, BSD, Apache, GPL, etc.)
   - Parse requirements.txt, package.json, pyproject.toml
   - Detect programming languages via GitHub API
   - Perform security risk scans (eval, exec, subprocess, etc.)

2. **Module Generation**
   - Generate `module.yaml` with:
     - Module name
     - Category
     - Entry script
     - Description (from README)
     - Inputs/outputs
     - Observer requirements

3. **Validation & Audit**
   - License validation against allowlist
   - Risk assessment with pattern matching
   - Duplicate detection
   - Tag attribution
   - PR text generation

4. **Repository Utilities** (`repo_utils.ts`)
   ```typescript
   - parseRepoUrl(url)          // Parse GitHub/GitLab URLs
   - analyzeReadme(repoUrl)      // Fetch and summarize README
   - detectLicense(repoUrl)      // Detect license type
   - parseRequirements(repoUrl)  // Extract dependencies
   - detectLanguages(repoUrl)    // Get language statistics
   - riskScan(repoUrl)           // Security risk analysis
   - licenseOk(name)             // Check license allowlist
   ```

### Key Files

1. **swisskiss_loader.ts** (main bot)
   - Processes GitHub URLs
   - Generates module YAML
   - Creates audit reports
   - Validates submissions

2. **repo_utils.ts** (utilities)
   - URL parsing
   - File fetching
   - License detection
   - Risk scanning

3. **schema.ts** (types)
   - Input/Output contracts
   - ModuleYaml structure
   - ModuleAudit structure

### How It Works

```typescript
Input: {
  url: "https://github.com/user/repo",
  category: "automation",
  bot_name: "my-bot"
}

Output: {
  status: "staged_for_review",
  module_yaml: { ... },
  audit: {
    license: "MIT",
    license_ok: true,
    requirements: [...],
    languages: { "Python": 12345 },
    risk_scan: { issues: [], count: 0 },
    summary: "README text..."
  },
  validation: { ... },
  confidence: 0.98
}
```

---

## Integration Options

### Option 1: Port SwissKiss to Python (Recommended)

**Pros:**
- Full control over implementation
- Integrate with existing Murphy backend
- Use Python LLM clients (Groq, Aristotle)
- Add to existing API endpoints

**Implementation Steps:**
1. Convert TypeScript to Python
2. Create `github_repo_loader.py`
3. Add API endpoints:
   - `POST /api/github/analyze` - Analyze repository
   - `POST /api/github/convert-to-module` - Convert to module
   - `GET /api/github/licenses` - Get license info
   - `GET /api/github/risks` - Get risk scan
4. Integrate with Artifact Generation System
5. Add UI panel for GitHub repo management

**Estimated Time:** 4-6 hours

### Option 2: Use Python Libraries

**Libraries Available:**
- `PyGithub` - GitHub API client
- `gitpython` - Git repository management
- `requests` - HTTP client for fetching files

**Implementation Steps:**
1. Install dependencies: `pip install PyGithub gitpython requests`
2. Create `github_integration.py`
3. Implement similar functionality to SwissKiss
4. Add API endpoints and UI

**Estimated Time:** 3-5 hours

### Option 3: Keep as Separate Bot (Minimal Integration)

**Approach:**
- Keep SwissKiss as standalone TypeScript bot
- Create interface to call bot from Murphy
- Store results in Murphy database
- Display in Murphy UI

**Pros:**
- Minimal changes to Murphy
- Reuse existing SwissKiss code

**Cons:**
- TypeScript runtime required
- More complex architecture

**Estimated Time:** 2-3 hours

---

## Proposed Implementation (Option 1 - Python Port)

### File Structure
```
/workspace/
├── github_repo_loader.py          # Main GitHub loader
├── github_repo_analyzer.py        # Analysis functions
├── github_risk_scanner.py         # Security scanning
├── github_module_generator.py     # Module YAML generation
└── murphy_backend_complete.py     # Add endpoints
```

### API Endpoints to Add
```python
# GitHub Repository Analysis
POST /api/github/analyze
  Input: { url, category, module_name }
  Output: { repo_info, analysis, risks, languages }

# Convert to Module
POST /api/github/convert-to-module
  Input: { repo_url, category, entry_script }
  Output: { module_yaml, audit, confidence }

# License Validation
GET /api/github/licenses/validate
  Input: { repo_url }
  Output: { license, allowed, issues }

# Risk Scan
POST /api/github/scan-risks
  Input: { repo_url }
  Output: { risks, issues, safe_to_use }

# Search GitHub
GET /api/github/search
  Input: { query, language, stars }
  Output: { repositories }
```

### UI Components to Add
```html
<!-- GitHub Repository Panel -->
<div id="github-repo-panel">
  <input type="text" id="repo-url" placeholder="GitHub URL">
  <button onclick="analyzeRepo()">Analyze</button>
  <button onclick="convertToModule()">Convert to Module</button>
  
  <div id="repo-analysis">
    <!-- License, languages, risks -->
  </div>
  
  <div id="module-preview">
    <!-- Generated module YAML -->
  </div>
</div>
```

### Terminal Commands
```
/github analyze <url>           # Analyze repository
/github convert <url>           # Convert to module
/github scan <url>              # Scan for risks
/github licenses                # List allowed licenses
/github search <query>          # Search GitHub
```

---

## Sample Implementation

### Basic GitHub Analyzer (Python)

```python
import requests
import re
from typing import Dict, List, Optional

ALLOWED_LICENSES = {'MIT', 'BSD', 'Apache', 'Apache-2.0', 'ISC', 'Unlicense', 'CC0'}

class GitHubRepoAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Murphy-GitHub-Loader/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def parse_repo_url(self, url: str) -> Dict[str, str]:
        """Parse GitHub URL into owner and repo"""
        pattern = r'github\.com/([^/]+)/([^/]+?)(\.git)?$'
        match = re.search(pattern, url)
        if match:
            return {
                'owner': match.group(1),
                'repo': match.group(2),
                'url': url
            }
        raise ValueError("Invalid GitHub URL")
    
    def fetch_raw_file(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Fetch raw file from GitHub"""
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
        response = self.session.get(url)
        return response.text if response.status_code == 200 else None
    
    def analyze_readme(self, owner: str, repo: str) -> str:
        """Fetch and summarize README"""
        for fname in ['README.md', 'README', 'readme.md']:
            content = self.fetch_raw_file(owner, repo, fname)
            if content:
                lines = content.split('\n')[:10]
                return '\n'.join(lines)
        return "No README found"
    
    def detect_license(self, owner: str, repo: str) -> str:
        """Detect repository license"""
        for fname in ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING']:
            content = self.fetch_raw_file(owner, repo, fname)
            if content:
                for license_name in ALLOWED_LICENSES:
                    if license_name.lower() in content.lower():
                        return license_name
                return 'UNKNOWN'
        return 'MISSING'
    
    def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get language statistics"""
        url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        response = self.session.get(url)
        return response.json() if response.status_code == 200 else {}
    
    def scan_risks(self, owner: str, repo: str) -> List[Dict]:
        """Scan for security risks"""
        risky_patterns = [
            (r'subprocess\.run', 'subprocess usage'),
            (r'os\.system', 'os.system usage'),
            (r'eval\(', 'eval() usage'),
            (r'exec\(', 'exec() usage'),
            (r'input\(', 'input() usage'),
        ]
        
        issues = []
        for fname in ['*.py', '*.js', '*.ts']:
            files = self.get_files(owner, repo, fname)
            for file_path in files:
                content = self.fetch_raw_file(owner, repo, file_path)
                if content:
                    for pattern, description in risky_patterns:
                        if re.search(pattern, content):
                            issues.append({
                                'file': file_path,
                                'pattern': pattern,
                                'description': description
                            })
        return issues
    
    def generate_module_yaml(self, repo_info: Dict, analysis: Dict) -> Dict:
        """Generate module.yaml from repo analysis"""
        return {
            'module_name': repo_info['repo'],
            'category': analysis.get('category', 'general'),
            'entry_script': 'main.py',
            'description': analysis.get('readme_summary', ''),
            'inputs': [],
            'outputs': [],
            'test_command': None,
            'observer_required': False,
            'source_url': repo_info['url']
        }
```

---

## Conclusion

**Current State:**
- ❌ GitHub repository-to-module functionality NOT available in current Murphy implementation
- ✅ Original system has SwissKiss Loader Bot (TypeScript) with full capabilities

**Recommended Action:**
Port the SwissKiss Loader functionality to Python and integrate it into the current Murphy System. This would provide:

1. **GitHub Repository Analysis**
   - Fetch README, license, requirements
   - Detect programming languages
   - Perform security risk scans

2. **Module Generation**
   - Generate module.yaml from repos
   - Create audit reports
   - Validate licenses and risks

3. **UI Integration**
   - GitHub repository panel
   - Terminal commands for repo operations
   - Visual module preview

**Estimated Implementation Time:** 4-6 hours for full Python port and integration.

---

**Would you like me to proceed with implementing the GitHub repository-to-module functionality?**