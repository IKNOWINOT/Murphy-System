# MFGC-AI: Murphy-Free Generative Control AI

**A Fully Functional Autonomous AI System with Provable Safety Guarantees**

**Copyright: All rights to Inoni LLC**  
**Contact: corey.gfc@gmail.com**

---

## 🎯 What is MFGC-AI?

MFGC-AI is a **complete, working implementation** of an autonomous AI control system that mathematically prevents catastrophic failures. Unlike traditional AI systems that react to errors, MFGC-AI **proactively prevents** them through formal control theory.

### Key Innovation

```
Authority(t) = Γ(Confidence(t))
Confidence(t) = w_g·G(x) + w_d·D(x) - κ·H(x)

IF Murphy_Index ↑ THEN Authority ↓
IF Instability ↑ THEN Gates ↑
IF Confidence < θ THEN Execution = FORBIDDEN
```

**The system cannot execute actions unless it has sufficient confidence and passes all safety gates.**

---

## ✨ Features

### ✅ Fully Implemented
- **7-Phase State Machine**: Expand → Type → Enumerate → Constrain → Collapse → Bind → Execute
- **Confidence Engine**: Real-time computation of G(x), D(x), H(x)
- **Safety Gate System**: 10+ gate types with automatic enforcement
- **Execution Packets**: Cryptographically signed with HMAC-SHA256
- **Terminal UI**: Black background with neon text indicators
- **Emergency Halt**: Automatic system shutdown on dangerous conditions
- **Phase Rollback**: Return to earlier phases when instability detected

### 🎨 Terminal Interface

The system features a beautiful terminal UI with:
- **Black background** for optimal visibility
- **Neon text colors** for different message types:
  - 👤 `u` = USER (cyan)
  - ✓ `v` = VERIFIED (green)
  - ◆ `d` = DETERMINED (blue)
  - ⚡ `g` = GENERATED (magenta)
  - ⚙ `s` = SYSTEM (yellow)
  - ✗ `e` = ERROR (red)

---

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install rich prompt-toolkit pyyaml networkx cryptography numpy torch transformers sentencepiece

# Run the demo
python -m mfgc_ai
```

### First Run

```bash
python -m mfgc_ai
```

You'll see the interactive terminal interface with real-time status updates.

---

## 📖 Interactive Commands

| Command | Description |
|---------|-------------|
| `status` | Show current system status |
| `cycle` | Run one control loop cycle |
| `auto` | Run automatic mode (continuous cycles) |
| `add` | Add a new artifact interactively |
| `artifacts` | Show all artifacts |
| `gates` | Show gate evaluation results |
| `confidence` | Show confidence breakdown |
| `phase` | Show current phase information |
| `packet` | Create execution packet |
| `demo` | Run automated demo sequence |
| `help` | Show help message |
| `quit` | Exit the system |

---

## 🎮 Try the Demo

```bash
python -m mfgc_ai
> demo
```

This will automatically demonstrate the full system lifecycle.

---

## 🏗️ Architecture

### Core Components

1. **Artifact Graph** - Stores hypotheses, evidence, decisions
2. **Confidence Engine** - Computes G(x), D(x), H(x)
3. **Gate System** - Enforces safety constraints
4. **Phase Controller** - Manages 7-phase lifecycle
5. **Execution System** - Cryptographic packet security
6. **Control Loop** - Main orchestration
7. **Terminal UI** - Interactive interface

---

## 📊 System Status Display

```
┌─ System Status ─────────────────────────────────────────────┐
│  Phase          TYPE                                         │
│  Confidence     0.48 [█████████░░░░░░░░░░░]                 │
│  Authority      0.48 [█████████░░░░░░░░░░░]                 │
│  Murphy Index   0.05 [█░░░░░░░░░░░░░░░░░░░]                 │
│  Safety Gates   ✓ PASSED                                     │
│  Artifacts      8                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Features

- **HMAC-SHA256 Signature**: Cryptographic verification
- **Time-Bounded Validity**: Packets expire after 5 minutes
- **Replay Prevention**: Each packet executes only once
- **Confidence Threshold**: Must be ≥ 0.85 to execute
- **Authority Bounds**: Maximum authority enforced

---

## 📚 Documentation

- **Installation Guide**: `README_INSTALL.md`
- **Project Abstract**: `MFGC-AI_PROJECT_ABSTRACT.md`
- **Implementation Guide**: `IMPLEMENTATION_GUIDE.md`
- **Contributor Guide**: `CONTRIBUTOR_GUIDE.md`

---

## 🤝 Contributing

This is a contributor-owned project with revenue sharing.

See `CONTRIBUTOR_GUIDE.md` for details.

---

## 📄 License

**Copyright: All rights to Inoni LLC**  
**Contact: corey.gfc@gmail.com**

---

## 💡 Why MFGC-AI?

### Traditional AI
```
AI → Action → Error → React → Damage Control
```

### MFGC-AI
```
AI → Confidence Check → Gate Evaluation → Safe Action
                ↓ (if low)              ↓ (if fail)
            Halt/Rollback           Prevent Execution
```

**Result**: Catastrophic failures are mathematically prevented.

---

## 📞 Contact

**Inoni LLC**  
Email: corey.gfc@gmail.com

---

**Built with provable safety guarantees. Murphy-free by design.** 🚀