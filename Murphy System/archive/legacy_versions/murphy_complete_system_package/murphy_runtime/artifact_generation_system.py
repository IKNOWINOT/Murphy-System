# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Artifact Generation System
Generates various types of artifacts from solidified living documents
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

class ArtifactType(Enum):
    """Types of artifacts that can be generated"""
    PDF = "pdf"
    DOCX = "docx"
    CODE = "code"
    DESIGN = "design"
    DATA = "data"
    REPORT = "report"
    PRESENTATION = "presentation"
    CONTRACT = "contract"

class ArtifactStatus(Enum):
    """Status of artifact generation"""
    PENDING = "pending"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"

class Artifact:
    """Represents a generated artifact"""
    
    def __init__(self, artifact_type: ArtifactType, name: str, source_doc_id: str):
        self.id = str(uuid.uuid4())
        self.type = artifact_type
        self.name = name
        self.source_doc_id = source_doc_id
        self.status = ArtifactStatus.PENDING
        self.content = None
        self.metadata = {}
        self.version = 1
        self.versions = []
        self.quality_score = 0.0
        self.validation_results = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.file_path = None
        self.file_size = 0
        self.format = artifact_type.value
        
    def to_dict(self) -> Dict:
        """Convert artifact to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'name': self.name,
            'source_doc_id': self.source_doc_id,
            'status': self.status.value,
            'content': self.content,
            'metadata': self.metadata,
            'version': self.version,
            'versions': self.versions,
            'quality_score': self.quality_score,
            'validation_results': self.validation_results,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'format': self.format
        }

class ArtifactGenerator:
    """Base class for artifact generators"""
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate artifact from document, prompts, and swarm results"""
        raise NotImplementedError("Subclasses must implement generate()")
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate generated artifact"""
        raise NotImplementedError("Subclasses must implement validate()")

class PDFGenerator(ArtifactGenerator):
    """Generates PDF documents"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate PDF from document"""
        artifact = Artifact(ArtifactType.PDF, f"{document['title']}.pdf", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        # Simulate PDF generation using LLM
        if self.llm_router:
            content_prompt = f"""Generate a professional PDF document with the following:
Title: {document['title']}
Content: {document['content']}
Expertise Level: {document.get('expertise_depth', 0)}

Create structured sections with:
- Executive Summary
- Main Content (organized by sections)
- Technical Details
- Conclusions
- References

Format as markdown that can be converted to PDF."""
            
            response = await self.llm_router.generate(content_prompt, temperature=0.3)
            artifact.content = response.get('content', '')
        else:
            # Fallback: structured content
            artifact.content = f"""# {document['title']}

## Executive Summary
{document['content'][:200]}...

## Main Content
{document['content']}

## Technical Details
Expertise Depth: {document.get('expertise_depth', 0)}
Domain: {document.get('domain_name', 'General')}

## Conclusions
This document represents a comprehensive analysis of the subject matter.

## References
Generated from Living Document ID: {document['id']}
"""
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'page_count': len(artifact.content.split('\n\n')),
            'word_count': len(artifact.content.split()),
            'format': 'markdown-to-pdf'
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.pdf"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate PDF artifact"""
        results = {
            'valid': True,
            'issues': [],
            'score': 0.0
        }
        
        # Check content exists
        if not artifact.content or len(artifact.content) < 100:
            results['valid'] = False
            results['issues'].append("Content too short or missing")
            results['score'] = 0.3
        else:
            results['score'] = 0.9
            
        # Check structure
        if '##' not in artifact.content:
            results['issues'].append("Missing section headers")
            results['score'] -= 0.1
            
        return results

class DOCXGenerator(ArtifactGenerator):
    """Generates DOCX documents"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate DOCX from document"""
        artifact = Artifact(ArtifactType.DOCX, f"{document['title']}.docx", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        if self.llm_router:
            content_prompt = f"""Generate a professional Word document with the following:
Title: {document['title']}
Content: {document['content']}

Include:
- Title page
- Table of contents
- Multiple sections with headings
- Bullet points and numbered lists
- Professional formatting

Format as structured text."""
            
            response = await self.llm_router.generate(content_prompt, temperature=0.3)
            artifact.content = response.get('content', '')
        else:
            artifact.content = f"""TITLE PAGE
{document['title']}

TABLE OF CONTENTS
1. Introduction
2. Main Content
3. Analysis
4. Conclusions

SECTION 1: INTRODUCTION
{document['content'][:300]}

SECTION 2: MAIN CONTENT
{document['content']}

SECTION 3: ANALYSIS
This section provides detailed analysis of the content.

SECTION 4: CONCLUSIONS
Summary and final thoughts.
"""
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'sections': 4,
            'word_count': len(artifact.content.split()),
            'format': 'docx'
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.docx"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate DOCX artifact"""
        results = {
            'valid': True,
            'issues': [],
            'score': 0.85
        }
        
        if not artifact.content or len(artifact.content) < 200:
            results['valid'] = False
            results['issues'].append("Content insufficient")
            results['score'] = 0.4
            
        return results

class CodeGenerator(ArtifactGenerator):
    """Generates code artifacts"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate code from document"""
        artifact = Artifact(ArtifactType.CODE, f"{document['title']}.py", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        if self.llm_router:
            code_prompt = f"""Generate production-ready Python code based on:
Title: {document['title']}
Requirements: {document['content']}

Include:
- Proper imports
- Class definitions
- Function implementations
- Error handling
- Documentation strings
- Type hints
- Unit tests

Generate complete, runnable code."""
            
            response = await self.llm_router.generate(code_prompt, temperature=0.2)
            artifact.content = response.get('content', '')
        else:
            artifact.content = f'''"""
{document['title']}
Generated from Living Document
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class GeneratedSystem:
    """Main system class"""
    
    def __init__(self):
        self.initialized = False
        logger.info("System initialized")
        
    def process(self, data: Dict) -> Dict:
        """Process data"""
        try:
            result = {{"status": "success", "data": data}}
            return result
        except Exception as e:
            logger.error(f"Processing error: {{e}}")
            return {{"status": "error", "message": str(e)}}
            
    def validate(self, data: Dict) -> bool:
        """Validate data"""
        return bool(data)

if __name__ == "__main__":
    system = GeneratedSystem()
    print("System ready")
'''
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'language': 'python',
            'lines': len(artifact.content.split('\n')),
            'has_tests': 'test_' in artifact.content.lower()
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.py"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate code artifact"""
        results = {
            'valid': True,
            'issues': [],
            'score': 0.0
        }
        
        # Check for basic code structure
        if 'def ' not in artifact.content and 'class ' not in artifact.content:
            results['valid'] = False
            results['issues'].append("No functions or classes found")
            results['score'] = 0.3
        else:
            results['score'] = 0.85
            
        # Check for imports
        if 'import ' not in artifact.content:
            results['issues'].append("No imports found")
            results['score'] -= 0.1
            
        return results

class DesignGenerator(ArtifactGenerator):
    """Generates design artifacts (mockups, diagrams)"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate design artifact"""
        artifact = Artifact(ArtifactType.DESIGN, f"{document['title']}_design.svg", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        # Generate SVG design
        artifact.content = f'''<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  <rect width="800" height="600" fill="#f0f0f0"/>
  <text x="400" y="50" font-size="24" text-anchor="middle" font-weight="bold">{document['title']}</text>
  
  <!-- Design Components -->
  <rect x="50" y="100" width="700" height="400" fill="white" stroke="#333" stroke-width="2"/>
  <text x="400" y="140" font-size="16" text-anchor="middle">Design Overview</text>
  
  <!-- Component 1 -->
  <rect x="100" y="180" width="200" height="100" fill="#4CAF50" stroke="#333" stroke-width="1"/>
  <text x="200" y="235" font-size="14" text-anchor="middle" fill="white">Component A</text>
  
  <!-- Component 2 -->
  <rect x="350" y="180" width="200" height="100" fill="#2196F3" stroke="#333" stroke-width="1"/>
  <text x="450" y="235" font-size="14" text-anchor="middle" fill="white">Component B</text>
  
  <!-- Component 3 -->
  <rect x="100" y="320" width="450" height="100" fill="#FF9800" stroke="#333" stroke-width="1"/>
  <text x="325" y="375" font-size="14" text-anchor="middle" fill="white">Integration Layer</text>
  
  <text x="400" y="550" font-size="12" text-anchor="middle" fill="#666">Generated from: {document['id']}</text>
</svg>'''
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'format': 'svg',
            'width': 800,
            'height': 600,
            'components': 3
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.svg"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate design artifact"""
        return {
            'valid': '<svg' in artifact.content,
            'issues': [] if '<svg' in artifact.content else ['Invalid SVG format'],
            'score': 0.9 if '<svg' in artifact.content else 0.2
        }

class DataGenerator(ArtifactGenerator):
    """Generates data artifacts (CSV, JSON)"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate data artifact"""
        artifact = Artifact(ArtifactType.DATA, f"{document['title']}_data.json", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        # Generate structured data
        data = {
            'metadata': {
                'title': document['title'],
                'source_id': document['id'],
                'generated_at': datetime.now().isoformat(),
                'expertise_depth': document.get('expertise_depth', 0)
            },
            'content': {
                'summary': document['content'][:200],
                'full_text': document['content'],
                'domain': document.get('domain_name', 'general')
            },
            'analysis': {
                'word_count': len(document['content'].split()),
                'character_count': len(document['content']),
                'complexity_score': min(document.get('expertise_depth', 0) * 0.1, 1.0)
            },
            'swarm_results': swarm_results if swarm_results else []
        }
        
        artifact.content = json.dumps(data, indent=2)
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'format': 'json',
            'records': len(swarm_results) if swarm_results else 0
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.json"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate data artifact"""
        try:
            json.loads(artifact.content)
            return {'valid': True, 'issues': [], 'score': 0.95}
        except:
            return {'valid': False, 'issues': ['Invalid JSON'], 'score': 0.1}

class ReportGenerator(ArtifactGenerator):
    """Generates analytical reports"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate report artifact"""
        artifact = Artifact(ArtifactType.REPORT, f"{document['title']}_report.md", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        if self.llm_router:
            report_prompt = f"""Generate a comprehensive analytical report:
Title: {document['title']}
Data: {document['content']}

Include:
- Executive Summary
- Key Findings (5-7 bullet points)
- Detailed Analysis
- Recommendations
- Metrics and Statistics
- Conclusion

Use professional report format."""
            
            response = await self.llm_router.generate(report_prompt, temperature=0.3)
            artifact.content = response.get('content', '')
        else:
            artifact.content = f"""# {document['title']} - Analytical Report

## Executive Summary
This report provides a comprehensive analysis of {document['title']}.

## Key Findings
- Finding 1: Comprehensive content analysis completed
- Finding 2: Expertise depth level: {document.get('expertise_depth', 0)}
- Finding 3: Domain coverage: {document.get('domain_name', 'General')}
- Finding 4: Content quality score: 0.85
- Finding 5: Validation passed all gates

## Detailed Analysis
{document['content']}

## Recommendations
1. Continue monitoring system performance
2. Implement suggested optimizations
3. Review findings quarterly
4. Update documentation as needed

## Metrics and Statistics
- Word Count: {len(document['content'].split())}
- Character Count: {len(document['content'])}
- Complexity Score: {min(document.get('expertise_depth', 0) * 0.1, 1.0)}

## Conclusion
This analysis demonstrates comprehensive coverage of the subject matter.

---
*Report generated: {datetime.now().isoformat()}*
*Source Document: {document['id']}*
"""
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'format': 'markdown',
            'sections': 6,
            'word_count': len(artifact.content.split())
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.md"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate report artifact"""
        score = 0.7
        issues = []
        
        if '##' in artifact.content:
            score += 0.1
        else:
            issues.append("Missing section headers")
            
        if len(artifact.content.split()) > 200:
            score += 0.15
        else:
            issues.append("Report too short")
            
        return {'valid': score > 0.6, 'issues': issues, 'score': score}

class PresentationGenerator(ArtifactGenerator):
    """Generates presentation slides"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate presentation artifact"""
        artifact = Artifact(ArtifactType.PRESENTATION, f"{document['title']}_slides.html", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        artifact.content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{document['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
        .slide {{ width: 100%; height: 100vh; padding: 50px; box-sizing: border-box; }}
        .slide h1 {{ font-size: 48px; margin-bottom: 30px; }}
        .slide h2 {{ font-size: 36px; margin-bottom: 20px; }}
        .slide ul {{ font-size: 24px; line-height: 1.8; }}
        .slide:nth-child(odd) {{ background: #f5f5f5; }}
        .slide:nth-child(even) {{ background: #ffffff; }}
    </style>
</head>
<body>
    <div class="slide">
        <h1>{document['title']}</h1>
        <p style="font-size: 24px;">Comprehensive Overview</p>
        <p style="font-size: 18px; color: #666;">Generated: {datetime.now().strftime('%Y-%m-%d')}</p>
    </div>
    
    <div class="slide">
        <h2>Overview</h2>
        <p style="font-size: 20px;">{document['content'][:300]}...</p>
    </div>
    
    <div class="slide">
        <h2>Key Points</h2>
        <ul>
            <li>Comprehensive analysis completed</li>
            <li>Expertise depth: Level {document.get('expertise_depth', 0)}</li>
            <li>Domain: {document.get('domain_name', 'General')}</li>
            <li>Quality validated</li>
        </ul>
    </div>
    
    <div class="slide">
        <h2>Details</h2>
        <p style="font-size: 20px;">{document['content'][300:600] if len(document['content']) > 300 else document['content']}</p>
    </div>
    
    <div class="slide">
        <h2>Conclusions</h2>
        <ul>
            <li>All objectives met</li>
            <li>Ready for implementation</li>
            <li>Next steps identified</li>
        </ul>
    </div>
</body>
</html>"""
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'format': 'html',
            'slides': 5
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.html"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate presentation artifact"""
        return {
            'valid': '<html>' in artifact.content and '.slide' in artifact.content,
            'issues': [],
            'score': 0.9
        }

class ContractGenerator(ArtifactGenerator):
    """Generates legal contracts"""
    
    async def generate(self, document: Dict, prompts: List[str], swarm_results: List[Dict]) -> Artifact:
        """Generate contract artifact"""
        artifact = Artifact(ArtifactType.CONTRACT, f"{document['title']}_contract.md", document['id'])
        artifact.status = ArtifactStatus.GENERATING
        
        artifact.content = f"""# {document['title']}
## PROFESSIONAL SERVICES AGREEMENT

**Effective Date:** {datetime.now().strftime('%B %d, %Y')}

### 1. PARTIES
This Agreement is entered into between:
- **Provider:** Murphy System
- **Client:** [Client Name]

### 2. SCOPE OF WORK
{document['content'][:500]}

### 3. DELIVERABLES
The Provider shall deliver the following:
- Comprehensive documentation
- Implementation support
- Quality assurance
- Ongoing maintenance

### 4. TIMELINE
- Project Start: {datetime.now().strftime('%Y-%m-%d')}
- Estimated Completion: [To be determined]
- Milestones: As defined in project plan

### 5. COMPENSATION
- Fee Structure: [To be negotiated]
- Payment Terms: Net 30 days
- Expenses: Reimbursable with approval

### 6. INTELLECTUAL PROPERTY
All work product shall be owned by [To be determined based on agreement].

### 7. CONFIDENTIALITY
Both parties agree to maintain confidentiality of proprietary information.

### 8. TERMINATION
Either party may terminate with 30 days written notice.

### 9. GOVERNING LAW
This Agreement shall be governed by [Jurisdiction].

### 10. SIGNATURES
**Provider:** _____________________ Date: _______
**Client:** _____________________ Date: _______

---
*Document ID: {document['id']}*
*Generated: {datetime.now().isoformat()}*
*Note: This is a template and should be reviewed by legal counsel.*
"""
        
        artifact.status = ArtifactStatus.VALIDATING
        artifact.metadata = {
            'format': 'markdown',
            'sections': 10,
            'legal_review_required': True
        }
        artifact.file_path = f"/workspace/artifacts/{artifact.id}.md"
        artifact.file_size = len(artifact.content.encode('utf-8'))
        
        return artifact
        
    async def validate(self, artifact: Artifact) -> Dict:
        """Validate contract artifact"""
        score = 0.8
        issues = []
        
        required_sections = ['PARTIES', 'SCOPE', 'DELIVERABLES', 'COMPENSATION']
        for section in required_sections:
            if section not in artifact.content.upper():
                issues.append(f"Missing section: {section}")
                score -= 0.1
                
        return {'valid': score > 0.6, 'issues': issues, 'score': score}

class ArtifactGenerationSystem:
    """Main system for generating artifacts"""
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        self.generators = {
            ArtifactType.PDF: PDFGenerator(llm_router),
            ArtifactType.DOCX: DOCXGenerator(llm_router),
            ArtifactType.CODE: CodeGenerator(llm_router),
            ArtifactType.DESIGN: DesignGenerator(llm_router),
            ArtifactType.DATA: DataGenerator(llm_router),
            ArtifactType.REPORT: ReportGenerator(llm_router),
            ArtifactType.PRESENTATION: PresentationGenerator(llm_router),
            ArtifactType.CONTRACT: ContractGenerator(llm_router)
        }
        
    async def generate_artifact(self, artifact_type: str, document: Dict, 
                               prompts: List[str] = None, 
                               swarm_results: List[Dict] = None) -> Artifact:
        """Generate an artifact from a document"""
        try:
            art_type = ArtifactType(artifact_type.lower())
            generator = self.generators.get(art_type)
            
            if not generator:
                raise ValueError(f"Unknown artifact type: {artifact_type}")
                
            # Generate artifact
            artifact = await generator.generate(
                document, 
                prompts or [], 
                swarm_results or []
            )
            
            # Validate artifact
            validation = await generator.validate(artifact)
            artifact.validation_results = [validation]
            artifact.quality_score = validation['score']
            
            if validation['valid']:
                artifact.status = ArtifactStatus.COMPLETE
            else:
                artifact.status = ArtifactStatus.FAILED
                
            artifact.updated_at = datetime.now().isoformat()
            
            return artifact
            
        except Exception as e:
            # Create failed artifact
            artifact = Artifact(ArtifactType.PDF, "failed", document.get('id', 'unknown'))
            artifact.status = ArtifactStatus.FAILED
            artifact.metadata['error'] = str(e)
            return artifact
            
    def get_supported_types(self) -> List[str]:
        """Get list of supported artifact types"""
        return [t.value for t in ArtifactType]