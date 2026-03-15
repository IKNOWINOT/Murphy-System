"""Injects avatar personality into prompts."""

from typing import Optional

from .avatar_models import AvatarProfile, UserAdaptation


class PersonaInjector:
    """Injects avatar personality into prompts."""

    def inject(
        self,
        base_prompt: str,
        avatar: AvatarProfile,
        adaptation: Optional[UserAdaptation] = None,
    ) -> str:
        """Build a persona-enriched prompt."""
        persona_parts = [
            f"You are {avatar.name}.",
            f"Your communication voice is {avatar.voice.value} and style is {avatar.style.value}.",
        ]
        if avatar.personality_traits:
            traits_str = ", ".join(
                f"{k}: {v:.1f}" for k, v in avatar.personality_traits.items()
            )
            persona_parts.append(f"Your personality traits: {traits_str}.")
        if avatar.knowledge_domains:
            persona_parts.append(
                f"You specialize in: {', '.join(avatar.knowledge_domains)}."
            )
        if adaptation:
            persona_parts.append(
                f"Preferred response length: {adaptation.preferred_response_length}."
            )
            if adaptation.preferred_formality > 0.7:
                persona_parts.append("Use formal language.")
            elif adaptation.preferred_formality < 0.3:
                persona_parts.append("Use casual, friendly language.")

        persona = " ".join(persona_parts)
        return f"{persona}\n\n{base_prompt}"

    def generate_greeting(self, avatar: AvatarProfile, user_name: str = "") -> str:
        """Generate a personalized greeting."""
        greeting = avatar.greeting_template.format(name=avatar.name)
        if user_name:
            greeting = greeting.rstrip(".!? ") + f", {user_name}!"
        return greeting
