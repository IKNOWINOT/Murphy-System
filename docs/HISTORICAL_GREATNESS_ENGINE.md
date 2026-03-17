# Historical Greatness Engine

**Module:** `src/historical_greatness_engine.py`  
**Design Label:** HGE-001  
**Owner:** Platform Engineering / Agent Intelligence  
**Tests:** `tests/test_historical_greatness_engine.py` (115 tests)  
**Introduced:** Round 57 — 2026-03-17

---

## Purpose

The Historical Greatness Engine codifies the **10 universal traits** shared by the most
successful people across every class in recorded history — and uses those traits as a
calibration layer for every role, agent, and org simulation in the Murphy System.

It answers the question:

> *What do Newton, Caesar, Jobs, Ali, Curie, Lincoln, da Vinci, Buffett, and Gandhi all
> have in common — and how does your role measure up?*

---

## The 10 Universal Traits of Historical Greatness

These traits were extracted by analysing 42+ historical greats across 10 classes spanning
2,500 years.  Every person who achieves defining, multi-generational impact demonstrates
all 10 traits — regardless of their domain.

| # | Trait | Core Question | Historical Epitome |
|---|-------|---------------|--------------------|
| 1 | **Obsessive Focus** | Can you say no to everything good to do the one great thing? | Isaac Newton |
| 2 | **Extreme Preparation** | Do you know the domain better than anyone who came before? | Napoleon Bonaparte |
| 3 | **Failure as Data** | Does failing make you faster or does it make you stop? | Thomas Edison |
| 4 | **Pattern Recognition** | Do you see what's really happening, not what everyone says? | Leonardo da Vinci |
| 5 | **Radical Self-Belief** | Can you hold your position when every authority disagrees? | Galileo Galilei |
| 6 | **Cross-Domain Learning** | How many fields outside your own are you actively studying? | Benjamin Franklin |
| 7 | **Narrative Mastery** | Can you make someone feel your vision as viscerally as you? | Winston Churchill |
| 8 | **Adaptive Strategy** | Can you change everything about *how* you win without changing *what* you win? | Jeff Bezos |
| 9 | **Network Leverage** | Is your network growing faster than your competition's? | Julius Caesar |
| 10 | **Long-Game Thinking** | Are you building a cathedral or decorating a tent? | Warren Buffett |

### Why These 10?

These are not soft skills or personality preferences.  They are the **structural invariants**
of greatness across every domain studied:

- Newton demonstrated obsessive focus *and* cross-domain learning *and* long-game thinking
- Caesar demonstrated network leverage *and* narrative mastery *and* adaptive strategy
- Edison demonstrated failure as data *and* extreme preparation *and* obsessive focus
- Da Vinci demonstrated pattern recognition *and* cross-domain learning *and* adaptive strategy

The pattern is universal.  The domain is incidental.

---

## Historical Greats Corpus

42+ modelled historical figures across 10 classes with per-trait scores (0–1):

| Class | Representative Greats |
|-------|-----------------------|
| **Military** | Alexander the Great, Napoleon, Sun Tzu, Eisenhower |
| **Business** | Carnegie, Rockefeller, Jobs, Bezos, Buffett, Ford |
| **Science** | Newton, Curie, Einstein, Tesla, Darwin |
| **Arts** | da Vinci, Michelangelo, Beethoven, Shakespeare |
| **Politics** | Lincoln, Churchill, Caesar, Marcus Aurelius, Mandela, Eleanor Roosevelt |
| **Athletics** | Ali, Michael Jordan, Serena Williams, Senna |
| **Philosophy** | Aristotle, Socrates, Franklin, Confucius |
| **Engineering** | Brunel, Edison, von Braun |
| **Spiritual** | Buddha, MLK, Gandhi |
| **Exploration** | Columbus, Earhart, Armstrong |

**Score calibration rules:**
- 1.00 = definitional example of this trait (used as the corpus reference)
- 0.95–0.99 = world-class, top 1% of all humans who ever lived in this domain
- 0.90–0.94 = elite; top 5%
- 0.80–0.89 = strong; top 20%
- 0.70–0.79 = functional; floor for historical greatness
- Every great scores ≥ 0.70 on every trait (universality requirement)

---

## Architecture

```
HistoricalGreatnessEngine          ← top-level façade
    │
    ├── TraitProfiler              ← maps competency scores → greatness traits
    │       │
    │       └── _COMPETENCY_TO_TRAITS  mapping (10 competencies → 10 traits)
    │
    ├── ArchetypeMatcher           ← finds closest historical great(s)
    │       │
    │       ├── class_champions()
    │       ├── top_n_all_time()
    │       └── trait_champions()
    │
    ├── GreatnessBenchmark         ← aggregated reference scores
    │       │
    │       ├── all_time_mean      ← mean across all 42+ greats
    │       ├── elite_threshold    ← mean of top-10 per trait
    │       └── per_class_means    ← mean per HistoricalClass
    │
    └── HISTORICAL_GREATS          ← Dict[str, HistoricalGreat] corpus
```

---

## Usage

### 1. Calibrate a role genome

```python
from elite_org_simulator import SkillGenome
from historical_greatness_engine import HistoricalGreatnessEngine

engine = HistoricalGreatnessEngine()
genome = SkillGenome.build("ceo")

result = engine.calibrate_genome(genome, subject_id="ceo")
print(result.archetype_match.name)     # → "Benjamin Franklin"
print(result.overall_greatness)        # → 0.9195
print(result.peak_trait)               # → (radical_self_belief, 0.9857)
```

### 2. Calibrate an entire org chart

```python
from elite_org_simulator import EliteOrgSimulator, CompanyStage

sim = EliteOrgSimulator()
chart = sim.build_chart(CompanyStage.SERIES_B)

# Full calibration through EliteOrgSimulator wrapper
calib = sim.calibrate_chart(chart)
print(calib["org_summary"]["avg_greatness_score"])    # → ~0.84
print(calib["org_summary"]["dominant_archetype"])     # → "Christopher Columbus"
```

### 3. Calibrate an agent persona

```python
result = engine.calibrate_agent(
    agent_id="alex_reeves",
    kaia_mix={"analytical": 0.25, "decisive": 0.40, "empathetic": 0.15,
              "creative": 0.10, "technical": 0.10},
    influence_frameworks=["cialdini_scarcity", "nlp_pacing_leading",
                          "carnegie_arouse_eager_want"],
)
print(result.archetype_match.name)
print(result.historical_class_alignment.value)
```

### 4. Generate a trait development plan

```python
calib = engine.calibrate_genome(SkillGenome.build("sales_manager"), subject_id="sm")
plan  = engine.trait_development_plan(calib, weeks=12)

for item in plan["development_plan"]:
    print(f"Priority {item['priority']}: Develop '{item['trait_name']}'")
    print(f"  Current: {item['current_score']:.2f} → Target: {item['target_score']:.2f}")
    print(f"  Weekly practice: {item['weekly_practice']}")
    print(f"  Anti-pattern to break: {item['anti_pattern_to_break']}")
    print(f"  Historical model: {item['historical_model']}")
```

### 5. Describe any trait in full detail

```python
info = engine.describe_trait(GreatnessTrait.OBSESSIVE_FOCUS)
print(info["description"])
print(info["epitome_quote"])
print(info["top_5_scorers"])
```

### 6. Find the archetype for any trait profile

```python
from historical_greatness_engine import ArchetypeMatcher, GreatnessTrait, ALL_TRAITS

matcher = ArchetypeMatcher()

# Who scores highest on each trait?
champions = matcher.trait_champions()
for trait, great in champions.items():
    print(f"{trait.value:<30} → {great.name}")

# Top 10 all-time
for great in matcher.top_n_all_time(10):
    print(f"{great.overall_score:.4f}  {great.name}")
```

---

## Competency → Trait Mapping

The `TraitProfiler` derives greatness traits from the 10 EliteOrgSimulator competency
dimensions using the following weighted mapping:

| Competency Dimension | Primary Trait (weight) | Secondary Traits |
|----------------------|------------------------|------------------|
| `strategic_thinking` | LONG_GAME_THINKING (0.40) | PATTERN_RECOGNITION (0.35), ADAPTIVE_STRATEGY (0.25) |
| `execution_speed` | EXTREME_PREPARATION (0.40) | OBSESSIVE_FOCUS (0.35), ADAPTIVE_STRATEGY (0.25) |
| `technical_depth` | OBSESSIVE_FOCUS (0.40) | EXTREME_PREPARATION (0.35), PATTERN_RECOGNITION (0.25) |
| `communication_clarity` | NARRATIVE_MASTERY (0.55) | NETWORK_LEVERAGE (0.25), ADAPTIVE_STRATEGY (0.20) |
| `data_fluency` | PATTERN_RECOGNITION (0.50) | FAILURE_AS_DATA (0.30), EXTREME_PREPARATION (0.20) |
| `customer_empathy` | NETWORK_LEVERAGE (0.35) | CROSS_DOMAIN_LEARNING (0.35), NARRATIVE_MASTERY (0.30) |
| `leadership_presence` | RADICAL_SELF_BELIEF (0.40) | NARRATIVE_MASTERY (0.35), NETWORK_LEVERAGE (0.25) |
| `cross_functional` | NETWORK_LEVERAGE (0.40) | CROSS_DOMAIN_LEARNING (0.35), ADAPTIVE_STRATEGY (0.25) |
| `persuasion_influence` | NETWORK_LEVERAGE (0.35) | NARRATIVE_MASTERY (0.35), RADICAL_SELF_BELIEF (0.30) |
| `adaptability` | ADAPTIVE_STRATEGY (0.50) | FAILURE_AS_DATA (0.30), CROSS_DOMAIN_LEARNING (0.20) |

---

## Integration with EliteOrgSimulator

The `EliteOrgSimulator` class wraps the engine transparently:

```python
sim = EliteOrgSimulator()

# calibrate_role() — single role by key
calib = sim.calibrate_role("vp_sales")

# calibrate_chart() — entire org chart
out = sim.calibrate_chart(chart)
```

Both methods delegate to the `HistoricalGreatnessEngine` internally, requiring no
additional configuration.  If `historical_greatness_engine.py` is unavailable (import
error), `calibrate_role()` returns `None` and `calibrate_chart()` returns
`{"error": "HistoricalGreatnessEngine not available"}`.

---

## Benchmark Reference Values

All-time mean trait scores across the 42-great corpus:

| Trait | All-Time Mean | Elite Threshold (top-10 mean) |
|-------|---------------|-------------------------------|
| Obsessive Focus | ~0.970 | ~0.995 |
| Extreme Preparation | ~0.938 | ~0.980 |
| Failure as Data | ~0.929 | ~0.975 |
| Pattern Recognition | ~0.960 | ~0.995 |
| Radical Self-Belief | ~0.960 | ~0.993 |
| Cross-Domain Learning | ~0.906 | ~0.963 |
| Narrative Mastery | ~0.912 | ~0.970 |
| Adaptive Strategy | ~0.921 | ~0.966 |
| Network Leverage | ~0.884 | ~0.960 |
| Long-Game Thinking | ~0.925 | ~0.985 |

*(Exact values computed at build time from `GreatnessBenchmark.build()`)*

---

## Class-Specific Signatures

Each historical class has a characteristic trait profile.  The top 3 traits most
elevated in each class:

| Class | Dominant Traits |
|-------|----------------|
| Military | Extreme Preparation, Adaptive Strategy, Radical Self-Belief |
| Business | Long-Game Thinking, Network Leverage, Obsessive Focus |
| Science | Obsessive Focus, Pattern Recognition, Failure as Data |
| Arts | Obsessive Focus, Narrative Mastery, Cross-Domain Learning |
| Politics | Narrative Mastery, Network Leverage, Adaptive Strategy |
| Athletics | Obsessive Focus, Extreme Preparation, Failure as Data |
| Philosophy | Cross-Domain Learning, Pattern Recognition, Long-Game Thinking |
| Engineering | Extreme Preparation, Failure as Data, Pattern Recognition |
| Spiritual | Long-Game Thinking, Radical Self-Belief, Narrative Mastery |
| Exploration | Radical Self-Belief, Extreme Preparation, Adaptive Strategy |

---

## Test Coverage

`tests/test_historical_greatness_engine.py` — **115 tests** across 15 parts:

| Part | Coverage |
|------|----------|
| 1 | GreatnessTrait enum completeness |
| 2 | HistoricalClass enum completeness |
| 3 | TraitDefinition content quality |
| 4 | HistoricalGreats corpus count, scores, universality |
| 5 | GreatnessBenchmark construction and math |
| 6 | SkillGenome → TraitProfiler calibration |
| 7 | ArchetypeMatcher methods |
| 8 | CalibrationResult completeness |
| 9 | Trait development plan generation |
| 10 | Agent calibration from KAIA + frameworks |
| 11 | EliteOrgSimulator HGE wiring |
| 12 | Org greatness summary consistency |
| 13 | Cross-class trait universality (≥ 0.70 floor) |
| 14 | Distance metrics and archetype ranking |
| 15 | describe_trait full content |

---

## Copyright

© 2020 Inoni Limited Liability Company  
Creator: Corey Post  
License: BSL 1.1
