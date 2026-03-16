"""Influence framework definitions for the self-selling pipeline.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations
import logging

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Influence Frameworks
# ---------------------------------------------------------------------------


@dataclass
class InfluenceFramework:
    """A codified influence principle that shapes agent behaviour.

    Each principle has:
    - A source (which book/framework it comes from)
    - A rule (the operational instruction for the LLM)
    - A trigger_condition (when this principle activates)
    - An action_template (what the agent does when triggered)
    """

    framework_id: str
    source: str  # "cialdini", "carnegie", "covey", "nlp", "mentalism", "habit_science"
    principle_name: str
    rule: str  # The LLM instruction
    trigger_condition: str  # When to use this
    action_template: str  # What the output looks like
    applicable_phases: List[str]  # Which selling phases this applies to


def _build_influence_frameworks() -> Dict[str, InfluenceFramework]:
    """Build the canonical library of influence frameworks."""
    frameworks: List[InfluenceFramework] = [
        # ------------------------------------------------------------------
        # Cialdini's Principles of Persuasion
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="cialdini_reciprocity",
            source="cialdini",
            principle_name="Reciprocity",
            rule=(
                "When contacting a prospect, always lead with value you've already "
                "provided or can provide for free. Never open with an ask."
            ),
            trigger_condition="First contact with any prospect",
            action_template=(
                "Lead with a free insight, audit, or deliverable specific to their business"
            ),
            applicable_phases=["outreach", "first_contact"],
        ),
        InfluenceFramework(
            framework_id="cialdini_social_proof",
            source="cialdini",
            principle_name="Social Proof",
            rule=(
                "Reference specific numbers: how many businesses Murphy is running "
                "automations for, how many emails sent today, how many state changes "
                "processed."
            ),
            trigger_condition="When prospect shows interest but hasn't committed",
            action_template="Include live system stats in the response",
            applicable_phases=["qualification", "nurture", "trial"],
        ),
        InfluenceFramework(
            framework_id="cialdini_authority",
            source="cialdini",
            principle_name="Authority",
            rule=(
                "Speak from demonstrated capability, not claimed capability. "
                "The system's own operational stats are the authority."
            ),
            trigger_condition="When prospect questions whether Murphy works",
            action_template=(
                "Pull real metrics from InoniBusinessAutomation.run_daily_automation() results"
            ),
            applicable_phases=["qualification", "trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="cialdini_commitment_consistency",
            source="cialdini",
            principle_name="Commitment & Consistency",
            rule=(
                "After a prospect takes any small action (replies, asks a question, opens a "
                "link), reference that action and build on it."
            ),
            trigger_condition="Any prospect engagement event",
            action_template=(
                "\"You asked about X — here's what Murphy found in the 4 hours since your question\""
            ),
            applicable_phases=["nurture", "trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="cialdini_liking",
            source="cialdini",
            principle_name="Liking",
            rule=(
                "Mirror the prospect's communication style. If they're casual, be casual. "
                "If they're formal, be formal. Use their vocabulary."
            ),
            trigger_condition="Every communication",
            action_template="Analyse prospect's writing style and match it",
            applicable_phases=["outreach", "qualification", "nurture", "trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="cialdini_scarcity",
            source="cialdini",
            principle_name="Scarcity",
            rule=(
                "The shadow agent deployed during trial has learned patterns specific to THIS "
                "prospect. Those patterns are lost if they don't convert."
            ),
            trigger_condition="End of trial period",
            action_template=(
                "\"Your shadow agent observed 47 workflow patterns unique to your business. "
                "Convert to keep it learning.\""
            ),
            applicable_phases=["conversion"],
        ),
        # ------------------------------------------------------------------
        # Carnegie's "How to Win Friends and Influence People"
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="carnegie_never_criticize",
            source="carnegie",
            principle_name="Never Criticize",
            rule=(
                "Never say the prospect's current process is bad. "
                "Say Murphy can augment what they already do well."
            ),
            trigger_condition="Any communication about their existing workflow",
            action_template=(
                "Acknowledge what they do well, then position Murphy as an amplifier"
            ),
            applicable_phases=["outreach", "qualification", "nurture", "trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="carnegie_honest_appreciation",
            source="carnegie",
            principle_name="Give Honest, Sincere Appreciation",
            rule=(
                "Acknowledge specific things the prospect's business does well "
                "before suggesting improvements."
            ),
            trigger_condition="Before any suggestion or pitch",
            action_template="Lead with a specific, genuine compliment about their business",
            applicable_phases=["outreach", "qualification", "trial"],
        ),
        InfluenceFramework(
            framework_id="carnegie_arouse_eager_want",
            source="carnegie",
            principle_name="Arouse Eager Want",
            rule=(
                "Frame everything in terms of what the prospect wants, not what Murphy does. "
                "Talk about THEIR time saved, THEIR revenue gained."
            ),
            trigger_condition="Any pitch or feature description",
            action_template="Translate every Murphy capability into a prospect outcome",
            applicable_phases=["outreach", "qualification", "nurture", "conversion"],
        ),
        InfluenceFramework(
            framework_id="carnegie_become_interested",
            source="carnegie",
            principle_name="Become Genuinely Interested",
            rule=(
                "Ask questions about their business before pitching. "
                "The first message should be 80% questions, 20% about Murphy."
            ),
            trigger_condition="First outreach or qualification call",
            action_template="Open with 3-4 specific questions about their business",
            applicable_phases=["outreach", "qualification"],
        ),
        InfluenceFramework(
            framework_id="carnegie_feel_important",
            source="carnegie",
            principle_name="Make the Other Person Feel Important",
            rule=(
                "Reference their specific business by name, their industry's unique challenges, "
                "their competitors."
            ),
            trigger_condition="Every outreach message",
            action_template="Personalise every message with their business name and industry context",
            applicable_phases=["outreach", "qualification", "nurture"],
        ),
        InfluenceFramework(
            framework_id="carnegie_let_them_talk",
            source="carnegie",
            principle_name="Let the Other Person Do the Talking",
            rule=(
                "In trial interactions, ask more questions than you answer. "
                "Route their responses into shadow agent learning."
            ),
            trigger_condition="Trial interaction or demo",
            action_template="End every message with an open question; log responses as training data",
            applicable_phases=["trial", "qualification"],
        ),
        # ------------------------------------------------------------------
        # Covey's "7 Habits of Highly Effective People"
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="covey_begin_with_end",
            source="covey",
            principle_name="Begin with the End in Mind",
            rule=(
                "Every communication should make clear what the prospect's end state looks "
                "like with Murphy running."
            ),
            trigger_condition="Any selling communication",
            action_template="Paint the post-Murphy picture first, then explain how to get there",
            applicable_phases=["outreach", "qualification", "nurture", "conversion"],
        ),
        InfluenceFramework(
            framework_id="covey_seek_to_understand",
            source="covey",
            principle_name="Seek First to Understand",
            rule=(
                "Before proposing any automation, demonstrate understanding of their current "
                "workflow by describing it back to them."
            ),
            trigger_condition="Before any automation proposal",
            action_template=(
                "Summarise their current workflow accurately before presenting a Murphy solution"
            ),
            applicable_phases=["qualification", "trial"],
        ),
        InfluenceFramework(
            framework_id="covey_think_win_win",
            source="covey",
            principle_name="Think Win-Win",
            rule=(
                "Frame the trial as zero-risk: 'If Murphy doesn't save you X hours, "
                "you've lost nothing. If it does, you've found your answer.'"
            ),
            trigger_condition="When prospect expresses hesitation about starting trial",
            action_template="Quantify the zero-risk: time to set up vs time to be saved",
            applicable_phases=["qualification", "trial"],
        ),
        InfluenceFramework(
            framework_id="covey_synergize",
            source="covey",
            principle_name="Synergize",
            rule=(
                "Show how Murphy's different engines work together for their specific "
                "business type, not as isolated features."
            ),
            trigger_condition="When explaining Murphy's capabilities",
            action_template=(
                "Describe a connected workflow using at least 3 Murphy engines in sequence"
            ),
            applicable_phases=["qualification", "nurture", "trial"],
        ),
        # ------------------------------------------------------------------
        # NLP Rapport Techniques
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="nlp_pacing_leading",
            source="nlp",
            principle_name="Pacing and Leading",
            rule=(
                "First match the prospect's current reality (pace), "
                "then introduce the new possibility (lead)."
            ),
            trigger_condition="Outreach composition",
            action_template=(
                "\"You're currently doing X manually [pace]. Imagine if that happened "
                "automatically while you focused on Y [lead].\""
            ),
            applicable_phases=["outreach", "qualification"],
        ),
        InfluenceFramework(
            framework_id="nlp_future_pacing",
            source="nlp",
            principle_name="Future Pacing",
            rule=(
                "Describe the prospect's life AFTER Murphy is running, "
                "in sensory-specific language."
            ),
            trigger_condition="Trial report delivery",
            action_template=(
                "\"Picture opening your laptop Monday morning and seeing every invoice already "
                "sent, every lead already scored.\""
            ),
            applicable_phases=["trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="nlp_anchoring",
            source="nlp",
            principle_name="Anchoring",
            rule=(
                "Always associate Murphy with their best business outcomes. "
                "When they mention a win, connect it to what Murphy could amplify."
            ),
            trigger_condition="When prospect mentions a positive business outcome",
            action_template="Connect their win to a Murphy capability that would scale it",
            applicable_phases=["qualification", "nurture", "trial", "conversion"],
        ),
        InfluenceFramework(
            framework_id="nlp_reframing",
            source="nlp",
            principle_name="Reframing",
            rule=(
                "When a prospect raises an objection, reframe it as a reason Murphy is needed."
            ),
            trigger_condition="Negative or sceptical response",
            action_template=(
                "\"I don't have time to set this up\" → "
                "\"That's exactly why Murphy exists — the setup IS Murphy's job.\""
            ),
            applicable_phases=["qualification", "trial", "conversion"],
        ),
        # ------------------------------------------------------------------
        # Mentalism / Cold Reading Techniques
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="mentalism_barnum_refined",
            source="mentalism",
            principle_name="Barnum Statements Refined by Data",
            rule=(
                "Start with universally true business challenges for their industry type, "
                "then narrow based on scraped data."
            ),
            trigger_condition="First contact",
            action_template=(
                "\"Most {business_type} businesses lose 15-20% of revenue to "
                "{common_pain_point}. Based on your website, you're likely dealing with "
                "{specific_inference}.\""
            ),
            applicable_phases=["outreach"],
        ),
        InfluenceFramework(
            framework_id="mentalism_rainbow_ruse",
            source="mentalism",
            principle_name="The Rainbow Ruse",
            rule=(
                "Acknowledge both sides: 'Your business probably has some processes that "
                "run smoothly and others that consume disproportionate time.'"
            ),
            trigger_condition="Any introductory or qualification communication",
            action_template=(
                "Lead with a balanced observation that prompts the prospect to confirm the pain"
            ),
            applicable_phases=["outreach", "qualification"],
        ),
        InfluenceFramework(
            framework_id="mentalism_hot_reading",
            source="mentalism",
            principle_name="Hot Reading from Public Data",
            rule=(
                "Scrape their website, LinkedIn, reviews, job postings. "
                "Reference specific details to demonstrate understanding."
            ),
            trigger_condition="Pre-outreach research phase",
            action_template=(
                "Include at least 2 specific references to publicly available data "
                "about their business in every first outreach"
            ),
            applicable_phases=["outreach"],
        ),
        # ------------------------------------------------------------------
        # Habit Science
        # ------------------------------------------------------------------
        InfluenceFramework(
            framework_id="habit_tiny_habits",
            source="habit_science",
            principle_name="Tiny Habits",
            rule=(
                "Don't ask for a big commitment. "
                "Ask them to reply with one sentence about their biggest time sink."
            ),
            trigger_condition="Call to action in any outreach message",
            action_template="End every message with a micro-ask: one question, one reply",
            applicable_phases=["outreach", "qualification"],
        ),
        InfluenceFramework(
            framework_id="habit_habit_stacking",
            source="habit_science",
            principle_name="Habit Stacking",
            rule=(
                "Attach Murphy to an existing habit: 'Every morning when you check email, "
                "Murphy has already sorted, categorised, and drafted responses.'"
            ),
            trigger_condition="When describing Murphy's daily value",
            action_template="Anchor Murphy's output to a routine the prospect already has",
            applicable_phases=["nurture", "trial"],
        ),
        InfluenceFramework(
            framework_id="habit_variable_reward",
            source="habit_science",
            principle_name="Variable Reward",
            rule=(
                "The trial report shows different insights each day, "
                "creating curiosity about what Day 3 will reveal."
            ),
            trigger_condition="Trial day report delivery",
            action_template=(
                "Each daily report surfaces a different insight, ending with a tease for tomorrow"
            ),
            applicable_phases=["trial"],
        ),
    ]
    return {fw.framework_id: fw for fw in frameworks}


#: The canonical library — import this to look up any framework by ID.
INFLUENCE_FRAMEWORKS: Dict[str, InfluenceFramework] = _build_influence_frameworks()
