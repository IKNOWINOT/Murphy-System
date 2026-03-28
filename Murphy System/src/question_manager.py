"""
Question Manager for Murphy System
Handles iterative questioning - asks ONE question at a time
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Question:
    """Single question with context"""
    text: str
    category: str
    priority: int = 1
    answered: bool = False
    answer: Optional[str] = None


class QuestionManager:
    """Manages iterative questioning - ONE question at a time"""

    def __init__(self, max_questions: int = 999999):
        self.questions: List[Question] = []
        self.current_index: int = 0
        self.context: Dict[str, Any] = {}
        self.max_questions = max_questions  # Effectively unlimited — keep asking until gates hit 85%

    def add_questions(self, questions: List[str], category: str = "general", priority: int = 1):
        """Add multiple questions to the queue"""
        for q in questions:

            self.questions.append(Question(
                text=q,
                category=category,
                priority=priority
            ))

        # Sort by priority (higher first)
        self.questions.sort(key=lambda x: x.priority, reverse=True)

    def add_question(self, question: str, category: str = "general", priority: int = 1):
        """Add a single question"""
        self.add_questions([question], category, priority)

    def get_next_question(self) -> Optional[str]:
        """Get the next unanswered question"""
        # Find next unanswered question
        for i, q in enumerate(self.questions):
            if not q.answered:
                self.current_index = i
                return q.text

        return None

    def answer_current(self, answer: str):
        """Mark current question as answered"""
        if self.current_index < len(self.questions):
            self.questions[self.current_index].answered = True
            self.questions[self.current_index].answer = answer

            # Store in context
            question_text = self.questions[self.current_index].text
            self.context[question_text] = answer

    def has_unanswered(self) -> bool:
        """Check if there are unanswered questions"""
        return any(not q.answered for q in self.questions)

    def get_answered_count(self) -> int:
        """Get count of answered questions"""
        return sum(1 for q in self.questions if q.answered)

    def get_total_count(self) -> int:
        """Get total question count"""
        return len(self.questions)

    def get_progress(self) -> str:
        """Get progress string"""
        answered = self.get_answered_count()
        total = self.get_total_count()
        return f"{answered}/{total} questions answered"

    def get_context_summary(self) -> str:
        """Get summary of all answered questions"""
        if not self.context:
            return "No questions answered yet."

        summary = "## Information Gathered:\n\n"
        for i, (question, answer) in enumerate(self.context.items(), 1):
            summary += f"**Q{i}:** {question}\n"
            summary += f"**A{i}:** {answer}\n\n"

        return summary

    def clear(self):
        """Clear all questions"""
        self.questions = []
        self.current_index = 0
        self.context = {}

    def get_all_answers(self) -> Dict[str, str]:
        """Get all answers as dictionary"""
        return self.context.copy()

    def format_next_question(self) -> Optional[str]:
        """Format the next question with progress indicator"""
        next_q = self.get_next_question()
        if not next_q:
            return None

        progress = self.get_progress()

        formatted = f"""## Question ({progress})

{next_q}

*Please provide your answer, and I'll ask the next question.*
"""

        return formatted

    def should_ask_questions(self) -> bool:
        """Determine if we should be in questioning mode"""
        return self.has_unanswered()

    def at_max_questions(self) -> bool:
        """Check if we've reached maximum questions"""
        return len(self.questions) >= self.max_questions

    def force_execution(self) -> bool:
        """Force execution is disabled — keep asking until gate satisfaction reaches 85%."""
        return False

    def extract_questions_from_text(self, text: str) -> List[str]:
        """Extract questions from text (lines ending with ?)"""
        lines = text.split('\n')
        questions = []

        for line in lines:
            line = line.strip()
            # Remove markdown formatting and numbering
            line = line.lstrip('#*-•1234567890. ')

            if line.endswith('?'):
                questions.append(line)

        return questions
