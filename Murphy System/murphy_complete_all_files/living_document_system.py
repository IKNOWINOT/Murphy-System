"""
Murphy System - Living Document Lifecycle

Documents that evolve from fuzzy/general to precise/specific through
intelligent operations (Magnify, Simplify, Solidify).
"""

import uuid
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json


class DocumentState(Enum):
    """States in the document lifecycle"""
    FUZZY = "fuzzy"              # Initial general state
    EXPANDING = "expanding"      # Adding detail
    CONTRACTING = "contracting"  # Removing detail
    TEMPLATE = "template"        # Reusable template
    SOLIDIFIED = "solidified"    # Ready for generation
    GENERATING = "generating"    # Being generated
    GENERATED = "generated"      # Output created
    ARCHIVED = "archived"        # Stored for reference


class DocumentType(Enum):
    """Types of documents"""
    PROPOSAL = "proposal"
    SPECIFICATION = "specification"
    REPORT = "report"
    PLAN = "plan"
    DESIGN = "design"
    CONTRACT = "contract"
    PRESENTATION = "presentation"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    CUSTOM = "custom"


@dataclass
class DocumentVersion:
    """A version of a document"""
    version: int
    state: DocumentState
    content: str
    expertise_depth: int  # 0 = fuzzy, higher = more detailed
    domains: List[str]
    modified_by: str  # 'system' or 'user'
    timestamp: datetime
    changes_summary: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'version': self.version,
            'state': self.state.value,
            'content': self.content,
            'expertise_depth': self.expertise_depth,
            'domains': self.domains,
            'modified_by': self.modified_by,
            'timestamp': self.timestamp.isoformat(),
            'changes_summary': self.changes_summary,
            'metadata': self.metadata
        }


@dataclass
class GenerativePrompt:
    """A prompt generated from a solidified document"""
    id: str
    document_id: str
    prompt_text: str
    swarm_type: str  # CREATIVE, ANALYTICAL, HYBRID, etc.
    domains: List[str]
    constraints: List[str]
    estimated_tokens: int
    created_at: datetime
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'document_id': self.document_id,
            'prompt_text': self.prompt_text,
            'swarm_type': self.swarm_type,
            'domains': self.domains,
            'constraints': self.constraints,
            'estimated_tokens': self.estimated_tokens,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class LivingDocument:
    """A document that evolves through its lifecycle"""
    id: str
    name: str
    doc_type: DocumentType
    description: str
    current_state: DocumentState
    current_version: int
    expertise_depth: int
    versions: List[DocumentVersion]
    created_at: datetime
    updated_at: datetime
    domains: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    generative_prompts: List[GenerativePrompt] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'doc_type': self.doc_type.value,
            'description': self.description,
            'current_state': self.current_state.value,
            'current_version': self.current_version,
            'expertise_depth': self.expertise_depth,
            'versions': [v.to_dict() for v in self.versions],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'domains': self.domains,
            'constraints': self.constraints,
            'tags': self.tags,
            'metadata': self.metadata,
            'generative_prompts': [p.to_dict() for p in self.generative_prompts]
        }
    
    def get_current_version(self) -> DocumentVersion:
        """Get the current version"""
        return self.versions[self.current_version - 1]
    
    def get_current_content(self) -> str:
        """Get current document content"""
        return self.get_current_version().content


class LivingDocumentSystem:
    """Manages living document lifecycle"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.documents: Dict[str, LivingDocument] = {}
        self.templates: Dict[str, LivingDocument] = {}
    
    def create_document(
        self,
        name: str,
        doc_type: str,
        description: str,
        initial_content: str,
        domains: List[str] = None,
        constraints: List[str] = None,
        tags: List[str] = None
    ) -> LivingDocument:
        """Create a new living document"""
        doc_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Create initial version (fuzzy state)
        initial_version = DocumentVersion(
            version=1,
            state=DocumentState.FUZZY,
            content=initial_content,
            expertise_depth=0,
            domains=domains or [],
            modified_by='user',
            timestamp=now,
            changes_summary='Initial document created'
        )
        
        # Create document
        document = LivingDocument(
            id=doc_id,
            name=name,
            doc_type=DocumentType[doc_type.upper()],
            description=description,
            current_state=DocumentState.FUZZY,
            current_version=1,
            expertise_depth=0,
            versions=[initial_version],
            created_at=now,
            updated_at=now,
            domains=domains or [],
            constraints=constraints or [],
            tags=tags or []
        )
        
        self.documents[doc_id] = document
        return document
    
    async def magnify(self, doc_id: str, domain: str) -> Dict:
        """Expand document with domain expertise"""
        document = self.documents.get(doc_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        current_content = document.get_current_content()
        current_version = document.get_current_version()
        
        # Use LLM to expand document
        if self.llm_client:
            prompt = f"""Expand this {document.doc_type.value} with {domain} domain expertise.

Current Content (Expertise Depth: {document.expertise_depth}):
{current_content}

Current Domains: {', '.join(document.domains)}

Add detailed {domain}-specific information, considerations, and best practices.
Increase the depth and specificity while maintaining clarity.

Respond in JSON format:
{{
    "expanded_content": "detailed content with {domain} expertise",
    "key_additions": ["addition 1", "addition 2", ...],
    "changes_summary": "Added {domain} expertise including..."
}}"""
            
            try:
                response = await self.llm_client.generate(prompt, temperature=0.6)
                result = json.loads(response)
                
                # Create new version
                new_version = DocumentVersion(
                    version=document.current_version + 1,
                    state=DocumentState.EXPANDING,
                    content=result['expanded_content'],
                    expertise_depth=document.expertise_depth + 1,
                    domains=document.domains + [domain] if domain not in document.domains else document.domains,
                    modified_by='system',
                    timestamp=datetime.now(),
                    changes_summary=result['changes_summary'],
                    metadata={'key_additions': result.get('key_additions', [])}
                )
                
                document.versions.append(new_version)
                document.current_version += 1
                document.current_state = DocumentState.EXPANDING
                document.expertise_depth += 1
                document.updated_at = datetime.now()
                
                if domain not in document.domains:
                    document.domains.append(domain)
                
                return {
                    'success': True,
                    'document': document.to_dict(),
                    'changes': result['changes_summary'],
                    'key_additions': result.get('key_additions', [])
                }
                
            except Exception as e:
                print(f"LLM magnify error: {e}")
                return self._simple_magnify(document, domain)
        else:
            return self._simple_magnify(document, domain)
    
    def _simple_magnify(self, document: LivingDocument, domain: str) -> Dict:
        """Simple magnify without LLM"""
        current_content = document.get_current_content()
        
        # Add domain-specific section
        expanded_content = f"""{current_content}

## {domain.title()} Domain Considerations

### Key Aspects
- {domain.title()}-specific requirements and standards
- Best practices in {domain} domain
- Common challenges and solutions
- Integration with {domain} systems

### Implementation Notes
- Ensure compliance with {domain} regulations
- Follow {domain} industry standards
- Consider {domain} optimization strategies
- Plan for {domain} scalability

### Next Steps
- Validate {domain} requirements
- Review {domain} constraints
- Consult {domain} experts
- Test {domain} integration"""
        
        new_version = DocumentVersion(
            version=document.current_version + 1,
            state=DocumentState.EXPANDING,
            content=expanded_content,
            expertise_depth=document.expertise_depth + 1,
            domains=document.domains + [domain] if domain not in document.domains else document.domains,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary=f"Added {domain} domain expertise"
        )
        
        document.versions.append(new_version)
        document.current_version += 1
        document.current_state = DocumentState.EXPANDING
        document.expertise_depth += 1
        document.updated_at = datetime.now()
        
        if domain not in document.domains:
            document.domains.append(domain)
        
        return {
            'success': True,
            'document': document.to_dict(),
            'changes': f"Added {domain} domain expertise",
            'key_additions': [
                f"{domain.title()}-specific requirements",
                f"Best practices in {domain}",
                f"Implementation notes for {domain}"
            ]
        }
    
    async def simplify(self, doc_id: str) -> Dict:
        """Distill document to essentials"""
        document = self.documents.get(doc_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        if document.expertise_depth == 0:
            return {
                'success': False,
                'error': 'Document is already at minimum depth'
            }
        
        current_content = document.get_current_content()
        
        # Use LLM to simplify document
        if self.llm_client:
            prompt = f"""Simplify this {document.doc_type.value} to its essential points.

Current Content (Expertise Depth: {document.expertise_depth}):
{current_content}

Remove unnecessary details, consolidate information, focus on core concepts.
Maintain the key message while reducing complexity.

Respond in JSON format:
{{
    "simplified_content": "concise content with essentials only",
    "removed_sections": ["section 1", "section 2", ...],
    "changes_summary": "Simplified by removing..."
}}"""
            
            try:
                response = await self.llm_client.generate(prompt, temperature=0.4)
                result = json.loads(response)
                
                # Create new version
                new_version = DocumentVersion(
                    version=document.current_version + 1,
                    state=DocumentState.CONTRACTING,
                    content=result['simplified_content'],
                    expertise_depth=max(0, document.expertise_depth - 1),
                    domains=document.domains,
                    modified_by='system',
                    timestamp=datetime.now(),
                    changes_summary=result['changes_summary'],
                    metadata={'removed_sections': result.get('removed_sections', [])}
                )
                
                document.versions.append(new_version)
                document.current_version += 1
                document.current_state = DocumentState.CONTRACTING
                document.expertise_depth = max(0, document.expertise_depth - 1)
                document.updated_at = datetime.now()
                
                return {
                    'success': True,
                    'document': document.to_dict(),
                    'changes': result['changes_summary'],
                    'removed_sections': result.get('removed_sections', [])
                }
                
            except Exception as e:
                print(f"LLM simplify error: {e}")
                return self._simple_simplify(document)
        else:
            return self._simple_simplify(document)
    
    def _simple_simplify(self, document: LivingDocument) -> Dict:
        """Simple simplify without LLM"""
        current_content = document.get_current_content()
        
        # Keep first few paragraphs and main sections
        lines = current_content.split('\n')
        essential_lines = []
        in_main_section = True
        
        for line in lines:
            # Keep headers and first few paragraphs
            if line.startswith('#') or (in_main_section and len(essential_lines) < 20):
                essential_lines.append(line)
            elif line.startswith('##'):
                in_main_section = False
        
        simplified_content = '\n'.join(essential_lines)
        if not simplified_content.strip():
            simplified_content = current_content[:500] + "\n\n[Content simplified to essentials]"
        
        new_version = DocumentVersion(
            version=document.current_version + 1,
            state=DocumentState.CONTRACTING,
            content=simplified_content,
            expertise_depth=max(0, document.expertise_depth - 1),
            domains=document.domains,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary=f"Simplified from depth {document.expertise_depth} to {max(0, document.expertise_depth - 1)}"
        )
        
        document.versions.append(new_version)
        document.current_version += 1
        document.current_state = DocumentState.CONTRACTING
        document.expertise_depth = max(0, document.expertise_depth - 1)
        document.updated_at = datetime.now()
        
        return {
            'success': True,
            'document': document.to_dict(),
            'changes': f"Simplified from depth {document.expertise_depth + 1} to {document.expertise_depth}",
            'removed_sections': ['Detailed subsections', 'Implementation notes', 'Extended examples']
        }
    
    def edit(self, doc_id: str, new_content: str, summary: str = None) -> Dict:
        """Apply user edits to document"""
        document = self.documents.get(doc_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        current_version = document.get_current_version()
        
        # Create new version with edits
        new_version = DocumentVersion(
            version=document.current_version + 1,
            state=current_version.state,  # Maintain current state
            content=new_content,
            expertise_depth=document.expertise_depth,
            domains=document.domains,
            modified_by='user',
            timestamp=datetime.now(),
            changes_summary=summary or 'User modifications applied'
        )
        
        document.versions.append(new_version)
        document.current_version += 1
        document.updated_at = datetime.now()
        
        return {
            'success': True,
            'document': document.to_dict(),
            'changes': new_version.changes_summary
        }
    
    async def solidify(self, doc_id: str) -> Dict:
        """Convert document to generative prompts"""
        document = self.documents.get(doc_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        current_content = document.get_current_content()
        
        # Use LLM to generate prompts
        if self.llm_client:
            prompt = f"""Convert this {document.doc_type.value} into generative prompts for content creation.

Document Content:
{current_content}

Domains: {', '.join(document.domains)}
Constraints: {', '.join(document.constraints)}

Create specific, actionable prompts that can be used to generate the final document.
Determine the best swarm type (CREATIVE, ANALYTICAL, HYBRID, etc.) for each section.

Respond in JSON format:
{{
    "prompts": [
        {{
            "section": "section name",
            "prompt": "detailed generation prompt",
            "swarm_type": "CREATIVE|ANALYTICAL|HYBRID",
            "estimated_tokens": 500
        }}
    ],
    "overall_strategy": "description of generation approach"
}}"""
            
            try:
                response = await self.llm_client.generate(prompt, temperature=0.5)
                result = json.loads(response)
                
                # Create generative prompts
                prompts = []
                for p in result.get('prompts', []):
                    prompt_obj = GenerativePrompt(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        prompt_text=p['prompt'],
                        swarm_type=p.get('swarm_type', 'HYBRID'),
                        domains=document.domains,
                        constraints=document.constraints,
                        estimated_tokens=p.get('estimated_tokens', 500),
                        created_at=datetime.now()
                    )
                    prompts.append(prompt_obj)
                
                document.generative_prompts = prompts
                document.current_state = DocumentState.SOLIDIFIED
                document.updated_at = datetime.now()
                
                # Create solidified version
                new_version = DocumentVersion(
                    version=document.current_version + 1,
                    state=DocumentState.SOLIDIFIED,
                    content=current_content,
                    expertise_depth=document.expertise_depth,
                    domains=document.domains,
                    modified_by='system',
                    timestamp=datetime.now(),
                    changes_summary=f"Solidified into {len(prompts)} generative prompts",
                    metadata={'overall_strategy': result.get('overall_strategy', '')}
                )
                
                document.versions.append(new_version)
                document.current_version += 1
                
                return {
                    'success': True,
                    'document': document.to_dict(),
                    'prompts': [p.to_dict() for p in prompts],
                    'strategy': result.get('overall_strategy', '')
                }
                
            except Exception as e:
                print(f"LLM solidify error: {e}")
                return self._simple_solidify(document)
        else:
            return self._simple_solidify(document)
    
    def _simple_solidify(self, document: LivingDocument) -> Dict:
        """Simple solidify without LLM"""
        current_content = document.get_current_content()
        
        # Create a single generative prompt
        prompt_obj = GenerativePrompt(
            id=str(uuid.uuid4()),
            document_id=document.id,
            prompt_text=f"Generate a complete {document.doc_type.value} based on this outline:\n\n{current_content}\n\nDomains: {', '.join(document.domains)}\nConstraints: {', '.join(document.constraints)}",
            swarm_type='HYBRID',
            domains=document.domains,
            constraints=document.constraints,
            estimated_tokens=1000,
            created_at=datetime.now()
        )
        
        document.generative_prompts = [prompt_obj]
        document.current_state = DocumentState.SOLIDIFIED
        document.updated_at = datetime.now()
        
        # Create solidified version
        new_version = DocumentVersion(
            version=document.current_version + 1,
            state=DocumentState.SOLIDIFIED,
            content=current_content,
            expertise_depth=document.expertise_depth,
            domains=document.domains,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary="Solidified into generative prompt"
        )
        
        document.versions.append(new_version)
        document.current_version += 1
        
        return {
            'success': True,
            'document': document.to_dict(),
            'prompts': [prompt_obj.to_dict()],
            'strategy': 'Single hybrid swarm generation'
        }
    
    def save_as_template(self, doc_id: str, template_name: str) -> Dict:
        """Save document as reusable template"""
        document = self.documents.get(doc_id)
        if not document:
            raise ValueError(f"Document {doc_id} not found")
        
        # Create template copy
        template_id = str(uuid.uuid4())
        template = LivingDocument(
            id=template_id,
            name=template_name,
            doc_type=document.doc_type,
            description=f"Template: {document.description}",
            current_state=DocumentState.TEMPLATE,
            current_version=document.current_version,
            expertise_depth=document.expertise_depth,
            versions=document.versions.copy(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            domains=document.domains.copy(),
            constraints=document.constraints.copy(),
            tags=document.tags.copy() + ['template'],
            metadata={'source_document': doc_id}
        )
        
        self.templates[template_id] = template
        
        return {
            'success': True,
            'template': template.to_dict(),
            'message': f"Template '{template_name}' created"
        }
    
    def create_from_template(self, template_id: str, name: str) -> Dict:
        """Create new document from template"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Create new document from template
        doc_id = str(uuid.uuid4())
        document = LivingDocument(
            id=doc_id,
            name=name,
            doc_type=template.doc_type,
            description=template.description,
            current_state=DocumentState.FUZZY,
            current_version=1,
            expertise_depth=template.expertise_depth,
            versions=[template.versions[0]],  # Start with first version
            created_at=datetime.now(),
            updated_at=datetime.now(),
            domains=template.domains.copy(),
            constraints=template.constraints.copy(),
            tags=template.tags.copy(),
            metadata={'template_id': template_id}
        )
        
        self.documents[doc_id] = document
        
        return {
            'success': True,
            'document': document.to_dict(),
            'message': f"Document '{name}' created from template"
        }
    
    def get_document(self, doc_id: str) -> Optional[LivingDocument]:
        """Get a document by ID"""
        return self.documents.get(doc_id)
    
    def list_documents(self, filters: Dict = None) -> List[LivingDocument]:
        """List all documents with optional filters"""
        docs = list(self.documents.values())
        
        if filters:
            if 'state' in filters:
                docs = [d for d in docs if d.current_state.value == filters['state']]
            if 'doc_type' in filters:
                docs = [d for d in docs if d.doc_type.value == filters['doc_type']]
            if 'domain' in filters:
                docs = [d for d in docs if filters['domain'] in d.domains]
            if 'tag' in filters:
                docs = [d for d in docs if filters['tag'] in d.tags]
        
        return docs
    
    def list_templates(self) -> List[LivingDocument]:
        """List all templates"""
        return list(self.templates.values())


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_living_documents():
        """Test the living document system"""
        system = LivingDocumentSystem()
        
        # Create a document
        doc = system.create_document(
            name="Business Proposal",
            doc_type="proposal",
            description="Comprehensive business proposal for new product",
            initial_content="We propose to develop a new product that solves customer pain points.",
            domains=["business"],
            tags=["proposal", "product"]
        )
        
        print(f"Created document: {doc.id}")
        print(f"State: {doc.current_state.value}, Depth: {doc.expertise_depth}")
        print()
        
        # Magnify with financial domain
        result = await system.magnify(doc.id, "financial")
        print(f"Magnified: {result['changes']}")
        print(f"Depth: {doc.expertise_depth}, Domains: {doc.domains}")
        print()
        
        # Magnify with marketing domain
        result = await system.magnify(doc.id, "marketing")
        print(f"Magnified: {result['changes']}")
        print(f"Depth: {doc.expertise_depth}, Domains: {doc.domains}")
        print()
        
        # Simplify
        result = await system.simplify(doc.id)
        print(f"Simplified: {result['changes']}")
        print(f"Depth: {doc.expertise_depth}")
        print()
        
        # Solidify
        result = await system.solidify(doc.id)
        print(f"Solidified: {result['strategy']}")
        print(f"Prompts: {len(result['prompts'])}")
        print(f"State: {doc.current_state.value}")
        print()
        
        # Save as template
        result = system.save_as_template(doc.id, "Business Proposal Template")
        print(f"Template created: {result['message']}")
        print()
        
        # Create from template
        result = system.create_from_template(result['template']['id'], "New Proposal")
        print(f"New document: {result['message']}")
    
    asyncio.run(test_living_documents())