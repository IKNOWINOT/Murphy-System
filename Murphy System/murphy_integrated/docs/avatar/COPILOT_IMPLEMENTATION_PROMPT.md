# Copilot Implementation Prompt — Murphy System Avatar Add-On

---

## HOW TO USE THIS PROMPT

Copy everything between the `=== BEGIN PROMPT ===` and `=== END PROMPT ===` markers and paste it directly into GitHub Copilot Chat (or Copilot Workspace). It is self-contained and gives Copilot everything it needs to build without asking clarifying questions.

---

=== BEGIN PROMPT ===

# Murphy System — Persistent Agent Avatar Identity Layer

You are working inside the **Murphy System** repository. The primary runtime folder is `Murphy System/murphy_integrated/`. Read and understand the existing architecture before writing any code. Do not invent new patterns — extend the ones already present.

---

## CODEBASE ORIENTATION — READ THESE FILES FIRST

Before writing anything, internalize these existing files:

```
Murphy System/murphy_integrated/src/governance_framework/agent_descriptor.py
Murphy System/murphy_integrated/src/shadow_agent_integration.py
Murphy System/murphy_integrated/src/event_backbone.py
Murphy System/murphy_integrated/src/delivery_adapters.py
Murphy System/murphy_integrated/src/rag_vector_integration.py
Murphy System/murphy_integrated/src/platform_connector_framework.py
Murphy System/murphy_integrated/src/comms/pipeline.py
Murphy System/murphy_integrated/src/comms/schemas.py
Murphy System/murphy_integrated/src/comms/connectors.py
Murphy System/murphy_integrated/src/groq_key_rotator.py
Murphy System/murphy_integrated/src/secure_key_manager.py
Murphy System/murphy_integrated/src/rbac_governance.py
Murphy System/murphy_integrated/src/social_media_moderation.py
Murphy System/murphy_integrated/src/compliance_engine.py
Murphy System/murphy_integrated/universal_control_plane.py
Murphy System/murphy_integrated/inoni_business_automation.py
Murphy System/murphy_integrated/murphy_complete_backend_extended.py
Murphy System/murphy_integrated/bots/kaia/internal/aionmind_core/core.ts
Murphy System/murphy_integrated/bots/CRMLeadGenerator_bot/crm.ts
Murphy System/murphy_integrated/bots/CRMLeadGenerator_bot/scoring.ts
Murphy System/murphy_integrated/bots/memory_manager_bot/
Murphy System/murphy_integrated/.env.example
Murphy System/murphy_integrated/requirements_murphy_1.0.txt
```

---

## EXISTING PATTERNS YOU MUST FOLLOW

### Pattern 1 — Agent Descriptor Extension
All agents are defined via `AgentDescriptor` in `src/governance_framework/agent_descriptor.py`. It uses `@dataclass` with `AuthorityBand`, `ActionSet`, `AccessMatrix`, `ResourceCaps`, `ConvergenceSpec`, `RetrySpec`, `SchedulingSpec`, and `TerminationSpec`. New agents must follow this exact schema.

### Pattern 2 — Shadow Agent Binding
`src/shadow_agent_integration.py` defines `ShadowAgent` with fields: `agent_id`, `primary_role_id`, `account_id`, `org_id`, `department`, `permissions`, `status`, `governance_boundary`. Avatar profiles bind to agents through this mechanism.

### Pattern 3 — Event Backbone
`src/event_backbone.py` defines `EventType(Enum)` and `Event(@dataclass)`. New events are added to the `EventType` enum. Handlers subscribe via `EventBackbone.subscribe(event_type, handler_fn)`. Never create a separate event system.

### Pattern 4 — Delivery Adapters
`src/delivery_adapters.py` defines `BaseDeliveryAdapter` with `validate(request) -> tuple[bool, List[str]]` and `deliver(request) -> DeliveryResult`. `VoiceDeliveryAdapter` already exists as a script-prep stub. Extend it — do not replace it.

### Pattern 5 — Platform Connectors
`src/platform_connector_framework.py` defines `ConnectorDefinition(@dataclass)`, `ConnectorInstance`, `ConnectorAction`, `ConnectorResult`, and `PlatformConnectorFramework`. All new third-party API connectors must register through this framework.

### Pattern 6 — API Key Rotation
`src/groq_key_rotator.py` defines `GroqKeyRotator` with `KeyStats(@dataclass)` and `get_next_key() -> tuple`. Clone this exact pattern for every new third-party API (ElevenLabs, HeyGen, Tavus, Vapi). Do not hardcode API keys anywhere.

### Pattern 7 — Comms Pipeline
`src/comms/pipeline.py` defines `MessageIngestor`, `IntentClassifier`, `RedactionPipeline`, `MessageStorage`, `ThreadManager`, `MessagePipeline`. New classifiers (sentiment) are added as pipeline stages, not separate systems.

### Pattern 8 — KaiaMix Persona (TypeScript bots)
TypeScript bots use `RunOpts = { name, systemPrompt, kaiaMix: { kiren, veritas, vallon } }`. The new `PersonaProfile` is a separate Python-side construct that generates the `systemPrompt` string injected into `RunOpts`.

### Pattern 9 — RAG Memory
`src/rag_vector_integration.py` defines `DocumentChunk`, `IngestedDocument`, `SearchResult`, `RAGVectorIntegration`. All memory operations go through this class. User-scoped memory adds `user_id` to `metadata` — it does not create a parallel memory system.

### Pattern 10 — Environment Config
All API keys go in `.env.example` as commented-out entries following the existing format. All config is loaded via `python-dotenv`. No hardcoded secrets anywhere.

---

## WHAT TO BUILD

Build the **Avatar Identity Layer** as a new module at:
```
Murphy System/murphy_integrated/src/avatar/
```

This module gives every Murphy agent a **persistent visual and voice identity** that automatically adapts its personality presentation based on what it knows about each specific user.

---

## FILE 1 — `src/avatar/__init__.py`

Export all public classes from the avatar module.

---

## FILE 2 — `src/avatar/avatar_models.py`

Create the following dataclasses using the same `@dataclass` + `field(default_factory=...)` pattern as `agent_descriptor.py`:

```python
@dataclass
class VoiceProfile:
    voice_id: str                    # ElevenLabs voice_id or PlayHT voice_id
    provider: str                    # "elevenlabs" | "playht" | "azure" | "openai"
    base_emotion: str                # "warm" | "professional" | "playful" | "authoritative"
    speaking_rate: float             # 0.5 - 2.0, default 1.0
    pitch_shift: float               # -1.0 to 1.0, default 0.0
    stability: float                 # ElevenLabs stability param, 0.0-1.0
    similarity_boost: float          # ElevenLabs similarity_boost param, 0.0-1.0
    cloned: bool                     # True if this is a cloned/custom voice
    sample_urls: List[str]           # Source audio samples used for cloning

@dataclass
class VisualProfile:
    avatar_id: str                   # HeyGen avatar_id or Tavus replica_id
    provider: str                    # "heygen" | "tavus" | "did"
    thumbnail_url: str               # Static preview image URL
    streaming_capable: bool          # Supports real-time streaming
    video_width: int                 # Default 1280
    video_height: int                # Default 720
    background_color: str            # Hex color or "transparent"
    created_from: str                # "photo" | "video" | "preset"

@dataclass
class PersonaProfile:
    persona_id: str
    name: str                        # Display name for this persona
    attachment_style: str            # "secure" | "anxious" | "avoidant" | "disorganized"
    humor_level: float               # 0.0 (none) to 1.0 (very humorous)
    assertiveness: float             # 0.0 (passive) to 1.0 (dominant)
    sensuality: float                # 0.0 (neutral) to 1.0 (flirtatious) — gated by compliance
    dominance: float                 # 0.0 (submissive) to 1.0 (commanding)
    warmth: float                    # 0.0 (cold/professional) to 1.0 (very warm)
    communication_style: str         # "direct" | "nurturing" | "flirtatious" | "educational" | "playful"
    voice_tone: str                  # "warm" | "professional" | "playful" | "authoritative" | "intimate"
    topics_of_interest: List[str]    # Topics this persona naturally gravitates toward
    forbidden_topics: List[str]      # Topics this persona never raises
    opening_style: str               # How this persona opens conversations
    closing_style: str               # How this persona ends conversations
    emoji_frequency: str             # "none" | "low" | "medium" | "high"
    message_length_preference: str   # "brief" | "moderate" | "detailed"

@dataclass
class UserPersonaVariant:
    variant_id: str
    user_id: str
    base_persona_id: str
    # Deltas from base persona — only fields that differ are set
    humor_level_delta: float         # Added to base humor_level
    warmth_delta: float              # Added to base warmth
    assertiveness_delta: float       # Added to base assertiveness
    preferred_topics: List[str]      # Topics this user responds well to
    avoided_topics: List[str]        # Topics this user disengages from
    preferred_message_length: str    # Observed preference
    preferred_emoji_frequency: str   # Observed preference
    response_time_preference: str    # "immediate" | "thoughtful" (based on user behavior)
    engagement_score: float          # 0.0-1.0 current engagement level
    purchase_intent_score: float     # 0.0-1.0 purchase likelihood
    churn_risk_score: float          # 0.0-1.0 churn likelihood
    vip_flag: bool                   # High-value user flag
    last_updated: datetime
    interaction_count: int
    notes: str                       # Free-text observations from agents

@dataclass
class AvatarProfile:
    avatar_profile_id: str
    agent_id: str                    # Links to AgentDescriptor
    display_name: str                # Public-facing name of this agent
    voice_profile: VoiceProfile
    visual_profile: VisualProfile
    base_persona: PersonaProfile
    user_variants: Dict[str, UserPersonaVariant]  # keyed by user_id
    platform_personas: Dict[str, str]  # platform -> persona_id overrides (e.g. "instagram" -> "playful_persona")
    compliance_tier: str             # "standard" | "adult" | "professional"
    ai_disclosure_text: str          # Mandatory disclosure text
    created_at: datetime
    updated_at: datetime
    version: int
    active: bool
```

---

## FILE 3 — `src/avatar/avatar_registry.py`

Create `AvatarRegistry` class that:
- Stores `AvatarProfile` objects in a thread-safe dict (use `threading.RLock()` like `rbac_governance.py`)
- Persists to SQLite/PostgreSQL using SQLAlchemy (follow the existing database pattern in the project)
- Methods:
  - `register(profile: AvatarProfile) -> str` — stores profile, returns `avatar_profile_id`
  - `get(avatar_profile_id: str) -> Optional[AvatarProfile]`
  - `get_by_agent(agent_id: str) -> Optional[AvatarProfile]`
  - `get_variant(agent_id: str, user_id: str) -> PersonaProfile` — returns adapted persona for this user, falls back to base persona if no variant exists
  - `update_variant(agent_id: str, user_id: str, variant: UserPersonaVariant) -> None`
  - `list_agents_with_avatars() -> List[str]`
  - `deactivate(avatar_profile_id: str) -> None`
  - `get_version_history(avatar_profile_id: str) -> List[Dict]`

---

## FILE 4 — `src/avatar/persona_injector.py`

Create `PersonaInjector` class that converts a `PersonaProfile` (and optional `UserPersonaVariant`) into a system prompt prefix string. This string is prepended to every agent's LLM system prompt.

The injector must:
- Accept `base_persona: PersonaProfile` and optional `user_variant: UserPersonaVariant`
- Merge variant deltas onto base persona values (clamped to 0.0-1.0)
- Generate a natural-language system prompt section describing the persona
- Include the `ai_disclosure_text` from `AvatarProfile` as a hidden instruction (not shown to user but enforced)
- Gate `sensuality > 0.3` behind `compliance_tier == "adult"` check — raise `ComplianceViolationError` if tier mismatch
- Output format:

```python
def build_system_prompt_prefix(
    self,
    base_persona: PersonaProfile,
    avatar_profile: AvatarProfile,
    user_variant: Optional[UserPersonaVariant] = None,
    platform: Optional[str] = None
) -> str:
    """Returns a system prompt prefix string ready to prepend to any agent's system prompt."""
```

Example output structure (the actual text should be natural, not JSON):
```
You are [display_name], an AI assistant. [ai_disclosure_text]

Your personality: You communicate in a [communication_style] style with [warmth_description] warmth. 
Your humor level is [humor_description]. You are [assertiveness_description].
You prefer [message_length_preference] messages and use emojis [emoji_frequency].
You naturally gravitate toward topics like [topics_of_interest].
You never discuss: [forbidden_topics].
[User-specific adaptations if variant provided]
```

---

## FILE 5 — `src/avatar/user_adaptation_engine.py`

Create `UserAdaptationEngine` class. This is the core of "avatars that adapt to specific users."

It reads from the existing `RAGVectorIntegration` (user-scoped memory) and generates/updates `UserPersonaVariant` objects.

```python
class UserAdaptationEngine:
    def __init__(self, rag: RAGVectorIntegration, avatar_registry: AvatarRegistry):
        ...

    def analyze_user(self, user_id: str, agent_id: str) -> UserPersonaVariant:
        """
        Reads user's conversation history from RAG memory (filtered by user_id),
        analyzes behavioral signals, and returns an updated UserPersonaVariant.
        
        Signals analyzed:
        - Average message length (preferred_message_length)
        - Emoji usage frequency (preferred_emoji_frequency)  
        - Topics mentioned most (preferred_topics)
        - Topics that caused disengagement (avoided_topics)
        - Response latency patterns (response_time_preference)
        - Engagement score from BehavioralScoringEngine
        - Purchase signals from conversation content
        - Churn signals (decreasing response frequency, shorter messages)
        """

    def update_variant_from_interaction(
        self,
        user_id: str,
        agent_id: str,
        message_text: str,
        sentiment_result: Dict,
        engagement_delta: float
    ) -> UserPersonaVariant:
        """
        Called after every interaction. Incrementally updates the variant
        based on the latest message. Uses exponential moving average for
        score updates (alpha=0.1 for stability).
        """

    def get_adapted_persona(self, agent_id: str, user_id: str) -> PersonaProfile:
        """
        Returns the fully merged PersonaProfile for this agent+user combination.
        Calls avatar_registry.get_variant() and applies deltas.
        """
```

---

## FILE 6 — `src/avatar/sentiment_classifier.py`

Create `SentimentClassifier` class. Add it as a stage in `src/comms/pipeline.py`'s `MessagePipeline` — do not create a parallel pipeline.

```python
@dataclass
class SentimentResult:
    valence: float          # -1.0 (very negative) to 1.0 (very positive)
    arousal: float          # 0.0 (calm) to 1.0 (excited/agitated)
    dominant_emotion: str   # "joy" | "anger" | "sadness" | "fear" | "surprise" | "disgust" | "neutral"
    intent_signal: str      # "buy" | "browse" | "complain" | "disengage" | "engage" | "question" | "neutral"
    confidence: float       # 0.0-1.0
    raw_text_preview: str   # First 100 chars of analyzed text

class SentimentClassifier:
    """
    Two-path classifier:
    - Fast path: VADER lexicon for sub-10ms classification (no API call)
    - Accurate path: Groq API call via existing GroqKeyRotator for nuanced cases
    
    Uses fast path by default. Switches to accurate path when:
    - Message length > 200 chars
    - Fast path confidence < 0.6
    - Message contains ambiguous signals
    
    Integrates with existing GroqKeyRotator from src/groq_key_rotator.py
    """
    
    def classify(self, text: str, fast_path: bool = True) -> SentimentResult: ...
    def classify_batch(self, texts: List[str]) -> List[SentimentResult]: ...
```

Wire `SentimentClassifier` into `MessagePipeline` in `src/comms/pipeline.py` so every `MessageArtifact` gets a `sentiment_result` field populated before reaching any agent.

Update `MessageArtifact` in `src/comms/schemas.py` to add:
```python
sentiment_result: Optional[SentimentResult] = None
```

---

## FILE 7 — `src/avatar/behavioral_scoring_engine.py`

Create `BehavioralScoringEngine`. This is separate from the existing `confidence_engine/risk/risk_scoring.py` (which scores task risk). This scores **user engagement and purchase intent**.

```python
@dataclass
class BehavioralScore:
    user_id: str
    agent_id: str
    engagement_score: float       # 0.0-1.0 — how engaged is this user right now
    purchase_intent_score: float  # 0.0-1.0 — likelihood to purchase/subscribe
    churn_risk_score: float       # 0.0-1.0 — likelihood to disengage
    vip_likelihood_score: float   # 0.0-1.0 — likelihood to be high-value
    computed_at: datetime
    signals_used: List[str]       # Which signals contributed to this score

class BehavioralScoringEngine:
    """
    Inputs per scoring call:
    - conversation_history: List of MessageArtifact (from comms/schemas.py)
    - sentiment_results: List of SentimentResult
    - response_latency_ms: float (how fast user responded)
    - message_length: int
    - emoji_count: int
    - question_count: int (questions asked by user = high engagement signal)
    - link_clicks: int (if tracked)
    - session_duration_s: float
    
    Fires EventType events when thresholds crossed:
    - engagement_score > 0.7 → fire HIGH_INTENT_SIGNAL event
    - purchase_intent_score > 0.8 → fire CONVERSION_TRIGGERED event  
    - churn_risk_score > 0.7 → fire CHURN_RISK event
    - vip_likelihood_score > 0.85 → fire VIP_FLAG event
    
    Uses EventBackbone from src/event_backbone.py — do not create a new event system.
    """
    
    def score(self, user_id: str, agent_id: str, **signals) -> BehavioralScore: ...
    def update_incremental(self, existing: BehavioralScore, new_signals: Dict) -> BehavioralScore: ...
```

---

## FILE 8 — `src/event_backbone.py` — EXTEND (do not rewrite)

Add these new `EventType` values to the existing `EventType(Enum)` class. Add them after the last existing entry:

```python
# Customer Journey Events (Avatar Add-On)
NEW_LEAD = "new_lead"
LEAD_QUALIFIED = "lead_qualified"
HIGH_INTENT_SIGNAL = "high_intent_signal"
SUBSCRIBED = "subscribed"
CHURN_RISK = "churn_risk"
VIP_FLAG = "vip_flag"
CONVERSION_TRIGGERED = "conversion_triggered"
UPSELL_OPPORTUNITY = "upsell_opportunity"
CALL_INITIATED = "call_initiated"
CALL_COMPLETED = "call_completed"
AVATAR_SESSION_STARTED = "avatar_session_started"
AVATAR_SESSION_ENDED = "avatar_session_ended"
PERSONA_ADAPTED = "persona_adapted"
SENTIMENT_FLAGGED = "sentiment_flagged"
```

---

## FILE 9 — `src/avatar/connectors/elevenlabs_connector.py`

Create ElevenLabs TTS connector following the `PlatformConnectorFramework` pattern from `src/platform_connector_framework.py`. Use `GroqKeyRotator` pattern from `src/groq_key_rotator.py` for API key rotation.

```python
class ElevenLabsConnector:
    """
    Registers with PlatformConnectorFramework as:
    ConnectorDefinition(
        connector_id="elevenlabs",
        name="ElevenLabs TTS",
        category=ConnectorCategory.CUSTOM,
        platform="elevenlabs",
        auth_type=AuthType.API_KEY,
        base_url="https://api.elevenlabs.io/v1",
        capabilities=["synthesize_text", "clone_voice", "list_voices", "stream_audio"]
    )
    """
    
    def synthesize_text(
        self,
        text: str,
        voice_id: str,
        emotion: str = "neutral",
        stability: float = 0.75,
        similarity_boost: float = 0.75,
        speaking_rate: float = 1.0,
        stream: bool = False
    ) -> bytes:
        """Returns audio bytes (MP3). If stream=True, returns generator of chunks."""
    
    def clone_voice(
        self,
        name: str,
        audio_sample_urls: List[str],
        description: str = ""
    ) -> str:
        """Uploads audio samples, creates cloned voice, returns voice_id."""
    
    def list_voices(self) -> List[Dict]:
        """Returns list of available voices with metadata."""
    
    def delete_voice(self, voice_id: str) -> bool:
        """Deletes a cloned voice."""
    
    def get_voice_settings(self, voice_id: str) -> Dict:
        """Returns current settings for a voice."""
```

Wire `ElevenLabsConnector` into the existing `VoiceDeliveryAdapter` in `src/delivery_adapters.py`:
- If `ELEVENLABS_API_KEY` is set in environment, use `ElevenLabsConnector.synthesize_text()` to produce actual audio
- Store audio bytes in `DeliveryResult.output["audio_bytes"]` (base64 encoded)
- Keep existing script-prep behavior as fallback when no API key is configured
- Do not break existing `VoiceDeliveryAdapter` tests

---

## FILE 10 — `src/avatar/connectors/heygen_connector.py`

Create HeyGen video avatar connector following the same `PlatformConnectorFramework` pattern.

```python
class HeyGenConnector:
    """
    Registers with PlatformConnectorFramework as connector_id="heygen"
    Base URL: https://api.heygen.com/v2
    """
    
    def create_avatar(
        self,
        name: str,
        photo_url: str = None,
        video_url: str = None
    ) -> str:
        """Creates a custom avatar from photo or video. Returns avatar_id."""
    
    def generate_video(
        self,
        avatar_id: str,
        script: str,
        voice_id: str,
        background_color: str = "#ffffff",
        width: int = 1280,
        height: int = 720
    ) -> Dict:
        """
        Submits video generation job.
        Returns: {"video_id": str, "status": "processing", "estimated_seconds": int}
        """
    
    def get_video_status(self, video_id: str) -> Dict:
        """
        Polls video generation status.
        Returns: {"status": "completed"|"processing"|"failed", "video_url": str}
        """
    
    def start_streaming_session(
        self,
        avatar_id: str,
        voice_id: str,
        quality: str = "high"
    ) -> Dict:
        """
        Starts a real-time streaming avatar session.
        Returns: {"session_id": str, "session_token": str, "sdp": str}
        """
    
    def send_streaming_text(self, session_id: str, text: str) -> bool:
        """Sends text to a live streaming session for the avatar to speak."""
    
    def end_streaming_session(self, session_id: str) -> bool:
        """Terminates a streaming session."""
    
    def list_avatars(self) -> List[Dict]:
        """Lists all available avatars for this account."""
```

---

## FILE 11 — `src/avatar/connectors/tavus_connector.py`

Create Tavus CVI (Conversational Video Interface) connector. This is the primary connector for user-personalized live video sessions.

```python
class TavusConnector:
    """
    Registers with PlatformConnectorFramework as connector_id="tavus"
    Base URL: https://tavusapi.com/v2
    
    Tavus CVI is purpose-built for AI-powered personalized video conversations.
    The persona_context parameter is where PersonaInjector output is passed.
    """
    
    def create_replica(
        self,
        replica_name: str,
        training_video_url: str,
        callback_url: str = None
    ) -> str:
        """Creates a Tavus replica (avatar) from training video. Returns replica_id."""
    
    def create_conversation(
        self,
        replica_id: str,
        persona_context: str,      # Output of PersonaInjector.build_system_prompt_prefix()
        user_context: Dict,        # User-specific data: name, preferences, history summary
        conversation_name: str = "",
        callback_url: str = None,
        max_duration_seconds: int = 3600
    ) -> Dict:
        """
        Creates a live CVI conversation session.
        Returns: {"conversation_id": str, "conversation_url": str, "status": "active"}
        The conversation_url is shared with the end user to join the video call.
        """
    
    def send_message(self, conversation_id: str, message: str) -> bool:
        """Injects a message into an active conversation."""
    
    def end_conversation(self, conversation_id: str) -> Dict:
        """
        Ends conversation and retrieves summary.
        Returns: {"duration_s": int, "transcript": str, "ended_at": str}
        """
    
    def get_conversation_status(self, conversation_id: str) -> Dict:
        """Returns current status and participant count."""
    
    def list_replicas(self) -> List[Dict]:
        """Lists all replicas for this account."""
```

---

## FILE 12 — `src/avatar/connectors/vapi_connector.py`

Create Vapi voice agent connector for live AI phone/voice calls.

```python
class VapiConnector:
    """
    Registers with PlatformConnectorFramework as connector_id="vapi"
    Base URL: https://api.vapi.ai
    
    Vapi handles real-time AI voice calls with LLM integration and function calling.
    """
    
    def create_assistant(
        self,
        name: str,
        system_prompt: str,        # Output of PersonaInjector.build_system_prompt_prefix()
        voice_id: str,             # ElevenLabs voice_id
        voice_provider: str = "11labs",
        first_message: str = "",
        end_call_phrases: List[str] = None,
        tools: List[Dict] = None   # Function calling tools
    ) -> str:
        """Creates a Vapi assistant configuration. Returns assistant_id."""
    
    def initiate_call(
        self,
        assistant_id: str,
        phone_number: str,
        context: Dict = None       # Injected as metadata into the call
    ) -> Dict:
        """
        Initiates an outbound call.
        Returns: {"call_id": str, "status": "queued", "estimated_start_s": int}
        """
    
    def handle_webhook(self, event_payload: Dict) -> None:
        """
        Processes Vapi webhook events (call.started, call.ended, transcript.update).
        On call.ended: extracts transcript, fires CALL_COMPLETED EventType,
        logs transcript to memory_manager_bot (user-scoped).
        """
    
    def get_transcript(self, call_id: str) -> Dict:
        """Returns full transcript with timestamps and speaker labels."""
    
    def get_call_analytics(self, call_id: str) -> Dict:
        """Returns call duration, sentiment summary, topics discussed."""
    
    def update_assistant(self, assistant_id: str, **kwargs) -> bool:
        """Updates assistant configuration (e.g., new persona after user adaptation)."""
```

---

## FILE 13 — `src/avatar/avatar_session_manager.py`

Create `AvatarSessionManager` that orchestrates the full lifecycle of a live avatar interaction.

```python
@dataclass
class AvatarSession:
    session_id: str
    agent_id: str
    user_id: str
    session_type: str              # "video" | "voice" | "text_with_avatar"
    provider: str                  # "tavus" | "heygen" | "vapi"
    external_session_id: str       # Provider's session/conversation/call ID
    persona_used: PersonaProfile   # The adapted persona for this session
    started_at: datetime
    ended_at: Optional[datetime]
    status: str                    # "active" | "ended" | "failed" | "fallback"
    fallback_reason: Optional[str] # Why fallback was triggered
    transcript: Optional[str]
    sentiment_summary: Optional[Dict]
    behavioral_score_delta: Optional[float]

class AvatarSessionManager:
    """
    Manages full avatar session lifecycle:
    1. Load AvatarProfile for agent
    2. Get adapted PersonaProfile for this user via UserAdaptationEngine
    3. Build system prompt via PersonaInjector
    4. Initiate session via appropriate connector (Tavus/HeyGen/Vapi)
    5. Monitor session health
    6. On session end: extract transcript, update user memory, update UserPersonaVariant
    7. Fire appropriate EventType events throughout
    
    Fallback chain: video → voice → text
    """
    
    def start_session(
        self,
        agent_id: str,
        user_id: str,
        session_type: str = "video",
        platform_override: str = None
    ) -> AvatarSession:
        """
        Starts a new avatar session.
        Fires AVATAR_SESSION_STARTED event.
        Returns session with join URL or call details.
        """
    
    def end_session(self, session_id: str) -> AvatarSession:
        """
        Ends session, retrieves transcript, updates memory and persona variant.
        Fires AVATAR_SESSION_ENDED event.
        Calls UserAdaptationEngine.update_variant_from_interaction().
        """
    
    def get_active_sessions(self, agent_id: str = None) -> List[AvatarSession]:
        """Returns all currently active sessions, optionally filtered by agent."""
    
    def handle_provider_webhook(self, provider: str, payload: Dict) -> None:
        """Routes incoming webhooks from Tavus/HeyGen/Vapi to correct session."""
```

---

## FILE 14 — `src/avatar/cost_ledger.py`

Create `CostLedger` for tracking third-party API costs and applying markup. Follow the `threading.RLock()` pattern from `rbac_governance.py`.

```python
@dataclass
class CostEntry:
    entry_id: str
    service: str               # "elevenlabs" | "heygen" | "tavus" | "vapi" | "openai" | "groq"
    operation: str             # "synthesize_text" | "generate_video" | "voice_call" | etc.
    units_consumed: float      # Characters, minutes, tokens, etc.
    unit_type: str             # "characters" | "minutes" | "tokens" | "videos"
    raw_cost_usd: float        # Actual API cost
    markup_rate: float         # e.g., 1.5 = 50% markup
    billable_amount_usd: float # raw_cost_usd * markup_rate
    customer_id: str
    agent_id: str
    session_id: str
    timestamp: datetime

class CostLedger:
    # Default markup rates per service
    DEFAULT_MARKUPS = {
        "elevenlabs": 1.5,     # 50% markup
        "heygen": 2.0,         # 100% markup
        "tavus": 2.0,          # 100% markup
        "vapi": 2.0,           # 100% markup
        "openai": 1.5,         # 50% markup
        "groq": 2.0,           # 100% markup
    }
    
    def record(self, entry: CostEntry) -> str: ...
    def get_customer_usage(self, customer_id: str, start_date: datetime, end_date: datetime) -> List[CostEntry]: ...
    def get_customer_total(self, customer_id: str, start_date: datetime, end_date: datetime) -> float: ...
    def set_markup_rate(self, service: str, rate: float) -> None: ...
    def get_summary_by_service(self, customer_id: str) -> Dict[str, float]: ...
    def check_daily_cap(self, customer_id: str, cap_usd: float) -> bool: ...
```

---

## FILE 15 — `.env.example` — EXTEND (do not rewrite)

Add these entries to the existing `.env.example` file after the existing social media section, following the exact comment format already used:

```bash
# ============= AVATAR & VOICE SERVICES (Optional) =============

# ElevenLabs (for agent voice synthesis and voice cloning)
# Get your key at: https://elevenlabs.io/app/settings/api-keys
# ELEVENLABS_API_KEY=your_elevenlabs_key_here
# ELEVENLABS_DEFAULT_VOICE_ID=your_default_voice_id

# HeyGen (for video avatar generation and streaming)
# Get your key at: https://app.heygen.com/settings/api
# HEYGEN_API_KEY=your_heygen_key_here

# Tavus (for personalized conversational video)
# Get your key at: https://platform.tavus.io/api-keys
# TAVUS_API_KEY=your_tavus_key_here

# Vapi (for AI voice calls)
# Get your key at: https://dashboard.vapi.ai/
# VAPI_API_KEY=your_vapi_key_here
# VAPI_PHONE_NUMBER=+1234567890

# PlayHT (alternative TTS provider)
# PLAYHT_API_KEY=your_playht_key_here
# PLAYHT_USER_ID=your_playht_user_id

# ============= AVATAR COST CONTROLS =============
# AVATAR_DAILY_COST_CAP_USD=50.00
# AVATAR_DEFAULT_MARKUP_RATE=2.0
# AVATAR_COMPLIANCE_TIER=standard
```

---

## FILE 16 — `src/avatar/api_routes.py`

Add new FastAPI routes for the avatar system. Register them in `murphy_complete_backend_extended.py` following the existing `@app.route()` pattern.

```python
# New endpoints to add:
POST   /api/avatar/profiles                    # Create avatar profile for an agent
GET    /api/avatar/profiles/{agent_id}         # Get avatar profile
PUT    /api/avatar/profiles/{agent_id}         # Update avatar profile
GET    /api/avatar/profiles/{agent_id}/persona/{user_id}  # Get adapted persona for user

POST   /api/avatar/sessions                    # Start avatar session
GET    /api/avatar/sessions/{session_id}       # Get session status
DELETE /api/avatar/sessions/{session_id}       # End session

POST   /api/avatar/webhooks/tavus              # Tavus webhook receiver
POST   /api/avatar/webhooks/heygen             # HeyGen webhook receiver
POST   /api/avatar/webhooks/vapi               # Vapi webhook receiver

GET    /api/avatar/costs/{customer_id}         # Get cost breakdown
GET    /api/avatar/costs/{customer_id}/summary # Get cost summary by service

POST   /api/avatar/voice/synthesize            # Direct TTS synthesis
GET    /api/avatar/voice/voices                # List available voices
```

---

## FILE 17 — `src/avatar/compliance_guard.py`

Create `AvatarComplianceGuard` that wraps the existing `ComplianceEngine` from `src/compliance_engine.py` with avatar-specific rules.

```python
class AvatarComplianceGuard:
    """
    Wraps existing ComplianceEngine with avatar-specific checks.
    Must be called before:
    - Any outbound social media message
    - Any avatar session initiation
    - Any persona profile creation with sensuality > 0
    
    Checks:
    1. AI disclosure is present in persona (never impersonate real humans)
    2. Sensuality level gated by compliance_tier
    3. Platform-specific content rules (Instagram, Twitter/X, Reddit TOS)
    4. Age verification requirement for adult compliance tier
    5. No real person's likeness used without consent flag
    """
    
    def check_persona(self, persona: PersonaProfile, avatar: AvatarProfile) -> Tuple[bool, List[str]]: ...
    def check_outbound_message(self, message: str, platform: str, persona: PersonaProfile) -> Tuple[bool, List[str]]: ...
    def check_session_initiation(self, session_type: str, user_id: str, avatar: AvatarProfile) -> Tuple[bool, List[str]]: ...
```

---

## DIRECTORY STRUCTURE TO CREATE

```
Murphy System/murphy_integrated/src/avatar/
├── __init__.py
├── avatar_models.py              # All dataclasses (AvatarProfile, PersonaProfile, etc.)
├── avatar_registry.py            # Persistent storage and lookup
├── persona_injector.py           # Converts PersonaProfile → system prompt string
├── user_adaptation_engine.py     # Reads memory, generates user-specific persona variants
├── sentiment_classifier.py       # Real-time sentiment on inbound messages
├── behavioral_scoring_engine.py  # Engagement/intent/churn scoring
├── avatar_session_manager.py     # Full session lifecycle orchestration
├── cost_ledger.py                # Third-party API cost tracking + markup
├── compliance_guard.py           # Avatar-specific compliance checks
├── api_routes.py                 # FastAPI route handlers
└── connectors/
    ├── __init__.py
    ├── elevenlabs_connector.py   # TTS + voice cloning
    ├── heygen_connector.py       # Video avatar + streaming
    ├── tavus_connector.py        # Personalized conversational video (CVI)
    └── vapi_connector.py         # Live AI voice calls
```

---

## INTEGRATION WIRING CHECKLIST

After creating all files above, make these modifications to existing files:

**`src/event_backbone.py`** — Add 14 new `EventType` values (listed in File 8 above)

**`src/delivery_adapters.py`** — Wire `ElevenLabsConnector` into `VoiceDeliveryAdapter.deliver()`. Keep existing behavior as fallback.

**`src/comms/pipeline.py`** — Add `SentimentClassifier` as a stage in `MessagePipeline` after `IntentClassifier`. Populate `MessageArtifact.sentiment_result`.

**`src/comms/schemas.py`** — Add `sentiment_result: Optional[SentimentResult] = None` to `MessageArtifact`.

**`src/shadow_agent_integration.py`** — Add `avatar_profile_id: Optional[str] = None` field to `ShadowAgent` dataclass.

**`src/governance_framework/agent_descriptor.py`** — Add `avatar_profile_id: Optional[str] = None` field to the main `AgentDescriptor` dataclass.

**`murphy_complete_backend_extended.py`** — Import and register `api_routes.py` routes.

**`requirements_murphy_1.0.txt`** — Add: `elevenlabs>=1.0.0`, `vapi-python>=0.1.0`, `vaderSentiment>=3.3.2`, `httpx>=0.25.0` (already present — verify)

**`.env.example`** — Add avatar service API key entries (listed in File 15 above)

---

## CODING STANDARDS TO FOLLOW

1. **All Python files**: Use `@dataclass` with `field(default_factory=...)` for mutable defaults — same as `agent_descriptor.py`
2. **Thread safety**: Use `threading.RLock()` for all shared state — same as `rbac_governance.py`
3. **Logging**: Use `logger = logging.getLogger(__name__)` at module level — same as all existing files
4. **Error handling**: Raise specific exceptions (not generic `Exception`). Create `AvatarError`, `PersonaComplianceError`, `ConnectorError` in `__init__.py`
5. **Type hints**: Full type hints on all public methods — same as `platform_connector_framework.py`
6. **Docstrings**: Triple-quoted docstrings on all classes and public methods
7. **No hardcoded secrets**: All API keys via `os.environ.get("KEY_NAME")` with clear error message if missing
8. **Connector pattern**: All third-party connectors must register with `PlatformConnectorFramework` from `src/platform_connector_framework.py`
9. **Event firing**: All significant state changes fire events via `EventBackbone` from `src/event_backbone.py`
10. **Cost recording**: Every third-party API call records to `CostLedger` before returning

---

## WHAT NOT TO DO

- Do NOT create a new event system — extend `EventType` in `event_backbone.py`
- Do NOT create a new memory system — extend `RAGVectorIntegration` with user namespacing
- Do NOT create a new connector framework — register with `PlatformConnectorFramework`
- Do NOT replace `VoiceDeliveryAdapter` — extend it with ElevenLabs as the synthesis backend
- Do NOT hardcode API keys, URLs, or model names
- Do NOT break existing tests in `tests/`
- Do NOT add new dependencies without adding them to `requirements_murphy_1.0.txt`
- Do NOT create TypeScript files for the avatar module — this is Python-side infrastructure
- Do NOT implement the social prospecting agents yet — that is a separate phase

=== END PROMPT ===