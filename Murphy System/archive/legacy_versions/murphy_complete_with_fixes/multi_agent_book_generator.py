"""
MULTI-AGENT BOOK GENERATION SYSTEM
True parallel processing with collective mind coordination
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

class WritingStyle(Enum):
    """Available writing styles"""
    ACADEMIC = "academic"
    CONVERSATIONAL = "conversational"
    TECHNICAL = "technical"
    STORYTELLING = "storytelling"
    PRACTICAL = "practical"
    INSPIRATIONAL = "inspirational"
    HUMOROUS = "humorous"
    AUTO = "auto"  # Let LLM decide

class ProcessingStage(Enum):
    """Three-stage processing"""
    MAGNIFY = "magnify"      # Expand complexity, add depth
    SIMPLIFY = "simplify"    # Select best parts, clarify
    SOLIDIFY = "solidify"    # Make it work for our system

@dataclass
class AgentProfile:
    """Each agent fills this out before starting"""
    agent_id: str
    role: str
    writing_style: WritingStyle
    expertise_areas: List[str]
    approach: str
    tone: str
    target_audience: str
    key_principles: List[str]
    
@dataclass
class ChapterTask:
    """Individual chapter task"""
    chapter_number: int
    title: str
    key_points: List[str]
    word_count_target: int
    assigned_agent: str
    dependencies: List[int]  # Which chapters must be done first
    
@dataclass
class ChapterOutput:
    """Output from a chapter agent"""
    chapter_number: int
    title: str
    content: str
    word_count: int
    key_concepts: List[str]
    references_to_other_chapters: List[int]
    stage: ProcessingStage
    agent_id: str
    timestamp: str

class CollectiveMind:
    """
    The coordinator that sees ALL information at once
    Ensures context matches across all chapters
    """
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.all_outputs: Dict[int, List[ChapterOutput]] = {}  # chapter_num -> [magnify, simplify, solidify]
        self.global_context: Dict = {}
        self.consistency_rules: List[str] = []
        
    def register_output(self, output: ChapterOutput):
        """Register a chapter output"""
        if output.chapter_number not in self.all_outputs:
            self.all_outputs[output.chapter_number] = []
        self.all_outputs[output.chapter_number].append(output)
        
    def analyze_global_context(self) -> Dict:
        """
        Analyze ALL outputs to extract:
        - Common themes
        - Terminology consistency
        - Concept flow
        - Cross-references
        """
        all_content = []
        all_concepts = []
        all_references = []
        
        for chapter_outputs in self.all_outputs.values():
            for output in chapter_outputs:
                all_content.append(output.content)
                all_concepts.extend(output.key_concepts)
                all_references.extend(output.references_to_other_chapters)
        
        # Use LLM to analyze global context
        analysis_prompt = f"""
        Analyze these book chapters for consistency:
        
        Total chapters: {len(self.all_outputs)}
        All concepts mentioned: {list(set(all_concepts))}
        Cross-references: {all_references}
        
        Identify:
        1. Common themes that should be consistent
        2. Terminology that must match across chapters
        3. Concept flow and logical progression
        4. Missing connections between chapters
        5. Inconsistencies in tone or style
        
        Return JSON with: themes, terminology, flow_issues, missing_connections, inconsistencies
        """
        
        try:
            response = self.llm_manager.generate(analysis_prompt)
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                self.global_context = json.loads(json_match.group())
            else:
                self.global_context = {
                    'themes': [],
                    'terminology': {},
                    'flow_issues': [],
                    'missing_connections': [],
                    'inconsistencies': []
                }
        except Exception as e:
            print(f"Error analyzing global context: {e}")
            self.global_context = {}
            
        return self.global_context
    
    def ensure_consistency(self, chapter_num: int, content: str) -> Tuple[bool, List[str]]:
        """
        Check if a chapter is consistent with global context
        Returns: (is_consistent, list_of_issues)
        """
        if not self.global_context:
            return True, []
        
        issues = []
        
        # Check terminology consistency
        terminology = self.global_context.get('terminology', {})
        for term, standard in terminology.items():
            if term.lower() in content.lower() and standard.lower() not in content.lower():
                issues.append(f"Use '{standard}' instead of '{term}' for consistency")
        
        # Check theme consistency
        themes = self.global_context.get('themes', [])
        for theme in themes:
            if theme.lower() not in content.lower():
                issues.append(f"Missing theme: {theme}")
        
        return len(issues) == 0, issues
    
    def get_context_for_chapter(self, chapter_num: int) -> Dict:
        """
        Get relevant context for a specific chapter
        Includes info from previous chapters and global themes
        """
        context = {
            'global_themes': self.global_context.get('themes', []),
            'terminology': self.global_context.get('terminology', {}),
            'previous_chapters': []
        }
        
        # Add summaries of previous chapters
        for num in range(1, chapter_num):
            if num in self.all_outputs:
                latest = self.all_outputs[num][-1]  # Get latest version
                context['previous_chapters'].append({
                    'number': num,
                    'title': latest.title,
                    'key_concepts': latest.key_concepts
                })
        
        return context

class ChapterAgent:
    """
    Individual agent that writes one chapter
    Goes through Magnify -> Simplify -> Solidify stages
    """
    
    def __init__(self, agent_id: str, profile: AgentProfile, llm_manager, collective_mind: CollectiveMind):
        self.agent_id = agent_id
        self.profile = profile
        self.llm_manager = llm_manager
        self.collective_mind = collective_mind
        
    async def write_chapter(self, task: ChapterTask) -> ChapterOutput:
        """
        Write a chapter through all three stages
        """
        print(f"\n[{self.agent_id}] Starting Chapter {task.chapter_number}: {task.title}")
        
        # Stage 1: MAGNIFY - Expand complexity, add depth
        magnified = await self._magnify_stage(task)
        self.collective_mind.register_output(magnified)
        
        # Stage 2: SIMPLIFY - Select best parts, clarify
        simplified = await self._simplify_stage(task, magnified)
        self.collective_mind.register_output(simplified)
        
        # Stage 3: SOLIDIFY - Make it work for our system
        solidified = await self._solidify_stage(task, simplified)
        self.collective_mind.register_output(solidified)
        
        return solidified
    
    async def _magnify_stage(self, task: ChapterTask) -> ChapterOutput:
        """
        MAGNIFY: Increase complexity, expand on all points
        Generate MORE information than needed
        """
        context = self.collective_mind.get_context_for_chapter(task.chapter_number)
        
        prompt = f"""
        AGENT PROFILE:
        {json.dumps(asdict(self.profile), indent=2)}
        
        TASK: Write Chapter {task.chapter_number} - {task.title}
        
        MAGNIFY STAGE - Generate EXTENSIVE content:
        - Expand on each key point with maximum detail
        - Add examples, case studies, research
        - Include multiple perspectives
        - Add depth and complexity
        - Target: {task.word_count_target * 2} words (we'll simplify later)
        
        Key Points to Cover:
        {json.dumps(task.key_points, indent=2)}
        
        Context from Previous Chapters:
        {json.dumps(context, indent=2)}
        
        Write in {self.profile.writing_style.value} style.
        Focus on {self.profile.expertise_areas}.
        
        Generate comprehensive content now:
        """
        
        content = self.llm_manager.generate(prompt)
        
        return ChapterOutput(
            chapter_number=task.chapter_number,
            title=task.title,
            content=content,
            word_count=len(content.split()),
            key_concepts=task.key_points,
            references_to_other_chapters=[],
            stage=ProcessingStage.MAGNIFY,
            agent_id=self.agent_id,
            timestamp=datetime.now().isoformat()
        )
    
    async def _simplify_stage(self, task: ChapterTask, magnified: ChapterOutput) -> ChapterOutput:
        """
        SIMPLIFY: Select best parts, clarify message
        Take expanded content and distill to essentials
        """
        # Check consistency with collective mind
        is_consistent, issues = self.collective_mind.ensure_consistency(
            task.chapter_number, 
            magnified.content
        )
        
        prompt = f"""
        SIMPLIFY STAGE - Distill to essentials:
        
        You wrote this expanded content:
        {magnified.content}
        
        Now SIMPLIFY:
        - Select the most impactful parts
        - Remove redundancy
        - Clarify the core message
        - Ensure logical flow
        - Target: {task.word_count_target} words
        
        {'CONSISTENCY ISSUES TO FIX:' + json.dumps(issues) if not is_consistent else 'Content is consistent with global context'}
        
        Global Context:
        {json.dumps(self.collective_mind.global_context, indent=2)}
        
        Produce simplified, focused content:
        """
        
        content = self.llm_manager.generate(prompt)
        
        return ChapterOutput(
            chapter_number=task.chapter_number,
            title=task.title,
            content=content,
            word_count=len(content.split()),
            key_concepts=task.key_points,
            references_to_other_chapters=[],
            stage=ProcessingStage.SIMPLIFY,
            agent_id=self.agent_id,
            timestamp=datetime.now().isoformat()
        )
    
    async def _solidify_stage(self, task: ChapterTask, simplified: ChapterOutput) -> ChapterOutput:
        """
        SOLIDIFY: Make it work specifically for our system
        Format, structure, add system-specific elements
        """
        prompt = f"""
        SOLIDIFY STAGE - Finalize for Murphy System:
        
        Simplified content:
        {simplified.content}
        
        Now SOLIDIFY:
        - Add proper markdown formatting
        - Include actionable takeaways
        - Add system-specific examples
        - Ensure it integrates with other chapters
        - Add cross-references where appropriate
        - Format for digital reading
        
        Produce final, polished content:
        """
        
        content = self.llm_manager.generate(prompt)
        
        # Extract key concepts and references
        key_concepts = self._extract_key_concepts(content)
        references = self._extract_references(content)
        
        return ChapterOutput(
            chapter_number=task.chapter_number,
            title=task.title,
            content=content,
            word_count=len(content.split()),
            key_concepts=key_concepts,
            references_to_other_chapters=references,
            stage=ProcessingStage.SOLIDIFY,
            agent_id=self.agent_id,
            timestamp=datetime.now().isoformat()
        )
    
    def _extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts from content"""
        # Simple extraction - look for bold terms, headings, etc.
        import re
        concepts = []
        
        # Find markdown headers
        headers = re.findall(r'#+\s+(.+)', content)
        concepts.extend(headers)
        
        # Find bold terms
        bold = re.findall(r'\*\*(.+?)\*\*', content)
        concepts.extend(bold)
        
        return list(set(concepts))[:10]  # Top 10
    
    def _extract_references(self, content: str) -> List[int]:
        """Extract chapter references"""
        import re
        refs = re.findall(r'Chapter\s+(\d+)', content)
        return [int(r) for r in refs if r != str(self.profile)]

class MultiAgentBookGenerator:
    """
    Main orchestrator for multi-agent book generation
    """
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.collective_mind = CollectiveMind(llm_manager)
        self.agents: Dict[str, ChapterAgent] = {}
        
    def ask_writing_style(self) -> WritingStyle:
        """
        Ask user for writing style preference
        Returns AUTO if not specified
        """
        print("\n" + "="*80)
        print("WRITING STYLE SELECTION")
        print("="*80)
        print("\nAvailable styles:")
        for i, style in enumerate(WritingStyle, 1):
            print(f"{i}. {style.value.upper()}")
        
        print("\nNote: If not specified, I'll use AUTO mode (LLM decides best style)")
        return WritingStyle.AUTO
    
    def create_agent_profiles(self, num_agents: int, writing_style: WritingStyle, book_topic: str) -> List[AgentProfile]:
        """
        Create agent profiles - each agent fills out their approach
        """
        profiles = []
        
        # Use LLM to generate diverse agent profiles
        prompt = f"""
        Create {num_agents} diverse writer agent profiles for a book about: {book_topic}
        
        Writing style: {writing_style.value}
        
        For each agent, specify:
        - Unique expertise areas
        - Specific approach to writing
        - Tone and voice
        - Target audience perspective
        - Key principles they follow
        
        Make them complementary - each brings different strengths.
        
        Return JSON array of {num_agents} agent profiles.
        """
        
        try:
            response = self.llm_manager.generate(prompt)
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                agent_data = json.loads(json_match.group())
                
                for i, data in enumerate(agent_data[:num_agents]):
                    profile = AgentProfile(
                        agent_id=f"agent_{i+1}",
                        role=data.get('role', f'Writer {i+1}'),
                        writing_style=writing_style,
                        expertise_areas=data.get('expertise_areas', []),
                        approach=data.get('approach', ''),
                        tone=data.get('tone', ''),
                        target_audience=data.get('target_audience', ''),
                        key_principles=data.get('key_principles', [])
                    )
                    profiles.append(profile)
        except Exception as e:
            print(f"Error creating agent profiles: {e}")
            # Fallback: create simple profiles
            for i in range(num_agents):
                profiles.append(AgentProfile(
                    agent_id=f"agent_{i+1}",
                    role=f"Writer {i+1}",
                    writing_style=writing_style,
                    expertise_areas=[book_topic],
                    approach="Clear and engaging",
                    tone="Professional",
                    target_audience="General readers",
                    key_principles=["Clarity", "Accuracy", "Engagement"]
                ))
        
        return profiles
    
    def plan_book_structure(self, book_topic: str, num_chapters: int = 9) -> List[ChapterTask]:
        """
        Plan the book structure - what each chapter covers
        """
        prompt = f"""
        Plan a {num_chapters}-chapter book about: {book_topic}
        
        For each chapter, specify:
        - Chapter number and title
        - 3-5 key points to cover
        - Target word count (aim for 2000-3000 words per chapter)
        - Dependencies (which chapters should be written first)
        
        Return JSON array of chapter plans.
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                chapter_data = json.loads(json_match.group())
                
                tasks = []
                for data in chapter_data[:num_chapters]:
                    task = ChapterTask(
                        chapter_number=data.get('chapter_number', len(tasks) + 1),
                        title=data.get('title', f'Chapter {len(tasks) + 1}'),
                        key_points=data.get('key_points', []),
                        word_count_target=data.get('word_count', 2500),
                        assigned_agent='',  # Will assign later
                        dependencies=data.get('dependencies', [])
                    )
                    tasks.append(task)
                
                return tasks
        except Exception as e:
            print(f"Error planning book structure: {e}")
            # Fallback: create simple structure
            return [
                ChapterTask(
                    chapter_number=i+1,
                    title=f"Chapter {i+1}",
                    key_points=[f"Point {j+1}" for j in range(3)],
                    word_count_target=2500,
                    assigned_agent='',
                    dependencies=[] if i == 0 else [i]
                )
                for i in range(num_chapters)
            ]
    
    async def generate_book(self, book_topic: str, book_title: str, num_chapters: int = 9) -> Dict:
        """
        Generate a complete book using multi-agent coordination
        
        Process:
        1. Ask for writing style (or use AUTO)
        2. Create agent profiles
        3. Plan book structure
        4. Assign chapters to agents
        5. Write chapters in parallel (respecting dependencies)
        6. Collective mind ensures consistency
        7. Assemble final book
        """
        print("\n" + "="*80)
        print(f"MULTI-AGENT BOOK GENERATION: {book_title}")
        print("="*80)
        
        # Step 1: Writing style
        writing_style = self.ask_writing_style()
        print(f"\nWriting style: {writing_style.value}")
        
        # Step 2: Create agent profiles
        print(f"\nCreating {num_chapters} agent profiles...")
        profiles = self.create_agent_profiles(num_chapters, writing_style, book_topic)
        
        for profile in profiles:
            print(f"\n{profile.agent_id}: {profile.role}")
            print(f"  Expertise: {', '.join(profile.expertise_areas)}")
            print(f"  Approach: {profile.approach}")
        
        # Step 3: Plan book structure
        print(f"\nPlanning {num_chapters}-chapter structure...")
        tasks = self.plan_book_structure(book_topic, num_chapters)
        
        for task in tasks:
            print(f"\nChapter {task.chapter_number}: {task.title}")
            print(f"  Key points: {', '.join(task.key_points)}")
            print(f"  Target words: {task.word_count_target}")
        
        # Step 4: Create agents and assign chapters
        print("\nCreating chapter agents...")
        for i, (profile, task) in enumerate(zip(profiles, tasks)):
            agent = ChapterAgent(profile.agent_id, profile, self.llm_manager, self.collective_mind)
            self.agents[profile.agent_id] = agent
            task.assigned_agent = profile.agent_id
        
        # Step 5: Write chapters in parallel (respecting dependencies)
        print("\nWriting chapters in parallel...")
        chapter_outputs = await self._write_chapters_parallel(tasks)
        
        # Step 6: Collective mind final analysis
        print("\nCollective mind analyzing global context...")
        global_context = self.collective_mind.analyze_global_context()
        print(f"Global themes: {global_context.get('themes', [])}")
        
        # Step 7: Assemble final book
        print("\nAssembling final book...")
        final_book = self._assemble_book(book_title, chapter_outputs, global_context)
        
        return final_book
    
    async def _write_chapters_parallel(self, tasks: List[ChapterTask]) -> Dict[int, ChapterOutput]:
        """
        Write chapters in parallel, respecting dependencies
        """
        completed = {}
        pending = {task.chapter_number: task for task in tasks}
        
        while pending:
            # Find tasks with satisfied dependencies
            ready = []
            for num, task in pending.items():
                deps_satisfied = all(dep in completed for dep in task.dependencies)
                if deps_satisfied:
                    ready.append(task)
            
            if not ready:
                print("Warning: Circular dependencies detected!")
                ready = list(pending.values())[:3]  # Force progress
            
            # Write ready chapters in parallel (max 9 at once)
            batch_size = min(9, len(ready))
            batch = ready[:batch_size]
            
            print(f"\nWriting batch of {len(batch)} chapters...")
            
            # Create tasks for parallel execution
            write_tasks = []
            for task in batch:
                agent = self.agents[task.assigned_agent]
                write_tasks.append(agent.write_chapter(task))
            
            # Execute in parallel
            results = await asyncio.gather(*write_tasks)
            
            # Register completed chapters
            for result in results:
                completed[result.chapter_number] = result
                if result.chapter_number in pending:
                    del pending[result.chapter_number]
                print(f"✓ Chapter {result.chapter_number} complete ({result.word_count} words)")
        
        return completed
    
    def _assemble_book(self, title: str, chapters: Dict[int, ChapterOutput], global_context: Dict) -> Dict:
        """
        Assemble final book from all chapters
        """
        # Sort chapters by number
        sorted_chapters = sorted(chapters.items())
        
        # Build full book content
        book_content = f"# {title}\n\n"
        book_content += "## Table of Contents\n\n"
        
        for num, output in sorted_chapters:
            book_content += f"{num}. {output.title}\n"
        
        book_content += "\n---\n\n"
        
        for num, output in sorted_chapters:
            book_content += f"## Chapter {num}: {output.title}\n\n"
            book_content += output.content
            book_content += "\n\n---\n\n"
        
        # Calculate stats
        total_words = sum(output.word_count for _, output in sorted_chapters)
        all_concepts = []
        for _, output in sorted_chapters:
            all_concepts.extend(output.key_concepts)
        
        return {
            'title': title,
            'content': book_content,
            'chapters': len(chapters),
            'total_words': total_words,
            'key_concepts': list(set(all_concepts)),
            'global_context': global_context,
            'generation_method': 'multi_agent_parallel',
            'timestamp': datetime.now().isoformat()
        }

# Integration function for Murphy system
async def generate_book_multi_agent(llm_manager, book_topic: str, book_title: str, num_chapters: int = 9) -> Dict:
    """
    Main entry point for multi-agent book generation
    """
    generator = MultiAgentBookGenerator(llm_manager)
    return await generator.generate_book(book_topic, book_title, num_chapters)