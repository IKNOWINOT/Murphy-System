# Architecture Overview - Murphy System Runtime

**Comprehensive system architecture documentation**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Dual-Plane Architecture](#dual-plane-architecture)
3. [Control Plane Components](#control-plane-components)
4. [Execution Plane Components](#execution-plane-components)
5. [Message Bus](#message-bus)
6. [Data Flows](#data-flows)
7. [Security Model](#security-model)
8. [Performance Characteristics](#performance-characteristics)

---

## Introduction

The Murphy System Runtime implements a revolutionary dual-plane architecture that physically separates reasoning from execution. This design ensures that generative AI systems cannot directly execute actions, preventing catastrophic failures through architectural constraints.

### Core Principles

1. **Physical Separation**: Control Plane (reasoning) and Execution Plane (action) are separate processes
2. **One-Way Communication**: Only Control Plane → Execution Plane via signed packets
3. **No Reverse Channel**: Execution Plane CANNOT send data back to Control Plane
4. **Cryptographic Verification**: All execution packets are HMAC-SHA256 signed
5. **Deterministic Execution**: Execution Plane uses FSM only, no generative inference

### Key Benefits

- **Safety**: Architectural impossibility of direct AI execution
- **Verifiability**: Cryptographic verification of all execution packets
- **Determinism**: Predictable execution behavior
- **Scalability**: Independent scaling of control and execution planes
- **Auditability**: Complete traceability of all execution decisions

---

## Dual-Plane Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL PLANE (Cloud)                    │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Exploration  │  │   Control    │  │  Confidence  │      │
│  │   Swarm      │  │   Swarm      │  │   Engine     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Gate        │  │  Phase       │  │  Packet      │      │
│  │  Compiler    │  │  Controller  │  │  Builder     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Artifact     │  │ Neuro-Symbolic│  │  Telemetry   │      │
│  │   Graph      │  │   Models     │  │   Learning   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Signed Packets Only
                            │ One-Way Communication
                            ↓
                    ┌──────────────┐
                    │  MESSAGE BUS │
                    │  (One-Way)   │
                    └──────────────┘
                            │
                            │ No Reverse Channel
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION PLANE (Edge)                    │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Packet      │  │ Deterministic│  │  Watchdog    │      │
│  │  Verifier    │  │    FSM       │  │   Timer      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Security    │  │  Resource    │  │  Emergency   │      │
│  │  Monitor     │  │  Monitor     │  │   Halt       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Communication Flow

1. **Control Plane** generates execution packets
2. **Packet Builder** cryptographically signs packets with HMAC-SHA256
3. **Message Bus** transmits signed packets (one-way only)
4. **Execution Plane** receives and verifies packets
5. **Packet Verifier** validates HMAC signature
6. **Deterministic FSM** executes actions if verified

### Key Architectural Guarantees

| Guarantee | Implementation | Benefit |
|-----------|----------------|---------|
| No Direct AI Execution | Physical separation of planes | Prevents AI from executing actions |
| Verified Execution | HMAC-SHA256 signing of all packets | Ensures packets originated from Control Plane |
| Deterministic Behavior | FSM-only execution plane | Predictable and auditable execution |
| No Feedback Loop | One-way message bus | Prevents AI from learning to bypass controls |
| Traceability | Complete packet logging | Full audit trail of all executions |

---

## Control Plane Components

### 1. Exploration Swarm

**Purpose**: Generate and explore hypotheses

**Functions**:
- EXPAND phase: Generate multiple hypotheses
- TYPE phase: Classify problem domains
- ENUMERATE phase: Enumerate solution options
- COLLAPSE phase: Propose best solutions

**Key Features**:
- Multi-agent exploration
- Parallel hypothesis generation
- Confidence scoring
- Evidence tracking

### 2. Control Swarm

**Purpose**: Identify failure modes and safety constraints

**Functions**:
- Identify potential failure modes
- Generate safety gates
- Assess risk levels
- Propose constraints

**Key Features**:
- Failure mode analysis
- Risk assessment
- Gate generation
- Constraint proposal

### 3. Confidence Engine

**Purpose**: Compute real-time confidence scores

**Computation**:
```
Confidence(t) = w_g·G(x) + w_d·D(x) - κ·H(x)

Where:
- G(x) = Goodness score (positive factors)
- D(x) = Domain alignment score
- H(x) = Hazard score (negative factors)
```

**Features**:
- Real-time confidence computation
- Multi-factor confidence scoring
- Adaptive confidence thresholds
- Confidence trend analysis

### 4. Gate Compiler

**Purpose**: Compile safety gates into executable checks

**Gate Types**:
- Regulatory compliance gates
- Security gates
- Performance gates
- Budget gates
- Timeline gates
- Quality gates

**Features**:
- Automatic gate generation
- Gate condition compilation
- Gate evaluation logic
- Gate enforcement mechanisms

### 5. Phase Controller

**Purpose**: Manage system phases and state transitions

**Phases**:
1. EXPAND - Generate hypotheses
2. TYPE - Classify problems
3. ENUMERATE - Enumerate options
4. CONSTRAIN - Apply constraints
5. COLLAPSE - Select best options
6. BIND - Bind to execution
7. EXECUTE - Execute actions

**Features**:
- Phase state management
- Phase transition logic
- Phase rollback capability
- Phase monitoring

### 6. Packet Builder

**Purpose**: Build and sign execution packets

**Packet Structure**:
```python
{
  "packet_id": "unique_id",
  "timestamp": "ISO_8601",
  "action": "action_to_execute",
  "parameters": {...},
  "signature": "HMAC-SHA256"
}
```

**Features**:
- Packet construction
- Cryptographic signing (HMAC-SHA256)
- Packet validation
- Packet serialization

### 7. Artifact Graph

**Purpose**: Store all hypotheses, evidence, and relationships

**Features**:
- Hypothesis storage
- Evidence tracking
- Relationship management
- Trust weight computation
- Provenance tracking

### 8. Neuro-Symbolic Models

**Purpose**: Hybrid neural-symbolic reasoning

**Features**:
- Knowledge graph management
- Rule-based inference
- Confidence scoring
- Learning from experience

### 9. Telemetry Learning

**Purpose**: Learn from system behavior and metrics

**Features**:
- Pattern recognition
- Anomaly detection
- Predictive analytics
- Trend analysis

---

## Execution Plane Components

### 1. Packet Verifier

**Purpose**: Verify cryptographic signatures of packets

**Verification Process**:
1. Extract signature from packet
2. Compute expected HMAC-SHA256
3. Compare signatures
4. Reject if signatures don't match

**Features**:
- Cryptographic verification
- Signature validation
- Packet integrity checking
- Replay attack prevention

### 2. Deterministic FSM

**Purpose**: Execute actions using finite state machine

**Execution Logic**:
- State transitions based on packet content
- No generative inference
- Deterministic behavior
- Predictable execution

**Features**:
- Finite state machine
- Deterministic state transitions
- No AI inference
- Verifiable execution

### 3. Watchdog Timer

**Purpose**: Monitor execution and prevent hanging

**Features**:
- Timeout monitoring
- Hanging detection
- Automatic recovery
- Emergency halt

### 4. Security Monitor

**Purpose**: Monitor for security violations

**Features**:
- Anomaly detection
- Intrusion detection
- Security policy enforcement
- Security event logging

### 5. Resource Monitor

**Purpose**: Monitor system resources

**Features**:
- CPU usage monitoring
- Memory usage monitoring
- Disk usage monitoring
- Resource limit enforcement

### 6. Emergency Halt

**Purpose**: Emergency system shutdown

**Trigger Conditions**:
- Packet verification failure
- Security violation detected
- Resource exhaustion
- Watchdog timeout
- Manual emergency stop

**Features**:
- Immediate system halt
- State preservation
- Alert generation
- Recovery procedures

---

## Message Bus

### Purpose

Provides a one-way communication channel from Control Plane to Execution Plane.

### Key Characteristics

- **One-Way Only**: Control Plane → Execution Plane
- **No Reverse Channel**: Execution Plane cannot send data back
- **Signed Packets**: All packets are cryptographically signed
- **Ordered Delivery**: Packets delivered in order
- **Persistent Queue**: Packets stored until verified

### Implementation

```python
# Message Bus Interface
class MessageBus:
    def send_packet(self, packet: ExecutionPacket) -> bool:
        """Send signed packet to execution plane"""
        pass
    
    def receive_packet(self) -> Optional[ExecutionPacket]:
        """Receive packet (execution plane only)"""
        pass
    
    def verify_packet(self, packet: ExecutionPacket) -> bool:
        """Verify packet signature"""
        pass
```

### Security Features

- Cryptographic verification of all packets
- Replay attack prevention
- Packet integrity checking
- Unauthorized packet rejection

---

## Data Flows

### System Building Flow

```
User Request
    ↓
Exploration Swarm (EXPAND)
    ↓
Exploration Swarm (TYPE)
    ↓
Exploration Swarm (ENUMERATE)
    ↓
Control Swarm (Identify Failure Modes)
    ↓
Gate Compiler (Create Safety Gates)
    ↓
Constraint Manager (Add Constraints)
    ↓
Exploration Swarm (COLLAPSE)
    ↓
Confidence Engine (Compute Confidence)
    ↓
Phase Controller (BIND)
    ↓
Packet Builder (Build & Sign Packet)
    ↓
Message Bus (Send Packet)
    ↓
Packet Verifier (Verify Signature)
    ↓
Deterministic FSM (Execute Action)
    ↓
Result
```

### Expert Generation Flow

```
User Request (Generate Experts)
    ↓
Exploration Swarm (Analyze Requirements)
    ↓
Exploration Swarm (Identify Expert Types)
    ↓
Control Swarm (Assess Risks)
    ↓
Gate Compiler (Create Expert Gates)
    ↓
Confidence Engine (Compute Confidence)
    ↓
Expert Compiler (Generate Experts)
    ↓
Result (Expert Team)
```

### Validation Flow

```
User Request (Validate System)
    ↓
Constraint Manager (Get All Constraints)
    ↓
Gate Compiler (Get All Gates)
    ↓
Constraint Validator (Validate Constraints)
    ↓
Gate Validator (Validate Gates)
    ↓
Confidence Engine (Compute Confidence)
    ↓
Result (Validation Report)
```

---

## Security Model

### Layered Security

```
┌─────────────────────────────────────┐
│  Application Layer (User Requests) │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│  Control Plane (Reasoning)          │
│  - Confidence Engine               │
│  - Safety Gates                    │
│  - Constraints                     │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│  Cryptographic Layer                │
│  - HMAC-SHA256 Signing              │
│  - Packet Verification              │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│  Message Bus (One-Way)              │
│  - No Reverse Channel               │
│  - Signed Packets Only             │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│  Execution Plane (Action)           │
│  - Deterministic FSM               │
│  - Security Monitor                │
│  - Watchdog Timer                  │
└─────────────────────────────────────┘
```

### Security Guarantees

1. **No Direct AI Execution**: AI cannot directly execute actions
2. **Verified Execution**: All actions verified via cryptography
3. **Deterministic Behavior**: Predictable execution via FSM
4. **No Learning Loop**: No feedback from execution to reasoning
5. **Complete Auditability**: Full traceability of all decisions

### Threat Mitigation

| Threat | Mitigation |
|--------|------------|
| AI executing unsafe actions | Physical separation of planes |
| Unauthorized packet execution | Cryptographic verification |
| AI learning to bypass controls | One-way communication |
| System hanging or crashing | Watchdog timer and emergency halt |
| Security violations | Security monitoring and enforcement |

---

## Performance Characteristics

### System Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Metric Collection | 21,484 ops/sec | 100 ops/sec | ✅ 215x above target |
| Adapter Initialization | 0.31ms | <2000ms | ✅ 6451x faster |
| Response Time | <1ms | <100ms | ✅ Sub-millisecond |
| Throughput | 20,000+ ops/sec | 1,000 ops/sec | ✅ 20x above target |
| Memory Overhead | 1.00 objects/operation | <10 objects/operation | ✅ 10x better |

### Enterprise Performance

| Scale | Roles | Compilation Time | Target | Status |
|-------|-------|-----------------|--------|--------|
| Small | 30 | 0.002s | <2s | ✅ 1000x faster |
| Medium | 100 | 0.005s | <5s | ✅ 1000x faster |
| Large | 500 | 0.020s | <15s | ✅ 750x faster |
| Enterprise | 1000 | 0.027s | <30s | ✅ Sub-second at scale |

### Memory Performance

| Scale | Roles | Memory Usage | Target | Status |
|-------|-------|--------------|--------|--------|
| Small | 30 | ~20MB | <50MB | ✅ 60% of target |
| Medium | 100 | ~50MB | <100MB | ✅ 50% of target |
| Large | 500 | ~100MB | <300MB | ✅ 33% of target |
| Enterprise | 1000 | ~150MB | <500MB | ✅ 30% of target |

### Scalability

- **Horizontal Scaling**: Independent scaling of control and execution planes
- **Vertical Scaling**: Efficient resource utilization
- **Caching**: Multi-level caching (L1, L2, L3) for optimal performance
- **Parallel Processing**: Batch processing with parallel compilation

---

## Next Steps

- [System Components](SYSTEM_COMPONENTS.md) - Detailed component descriptions
- [Data Flows](DATA_FLOWS.md) - Detailed data flow documentation
- [Interfaces](INTERFACES.md) - System interfaces and protocols

---

**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**
---

## Known Technical Debt

### Bot Shim Duplication (TD-001)

**Severity:** Medium | **Created:** 2026-03-11

The `bots/` directory contains 20+ Cloudflare Worker bots, each of which ships its own copy of the following shim files:

| File | Purpose |
|------|---------|
| `internal/shim_quota.ts` | Per-key request quota tracking via KV |
| `internal/shim_stability.ts` | Availability / health reporting |
| `internal/shim_budget.ts` | Token-budget accounting |
| `internal/metrics.ts` | Structured event emission |
| `internal/db/audit.ts` or `events.ts` | D1 audit-event insertion |

These files are nearly identical across all bots; any bug fix or improvement must be manually applied to every copy. Recent security fixes (e.g. adding `console.error` logging to the bare `catch{}` blocks in audit files — Issue 57) required touching all four `events.ts`/`audit.ts` files individually.

**Recommended resolution:** Extract the shared shim logic into a private npm package (e.g. `@murphy/bot-shims`) and have each bot import from it. Until that refactor is complete, treat any change to one shim file as a signal to update all peer copies.

**Tracking:** Issue 59 (Round 6 deep-scan gap closure)
