# Murphy System User Guide

## Welcome to Murphy System

Murphy System is an intelligent task execution platform that learns from your corrections and continuously improves its decision-making capabilities.

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [Using the System](#using-the-system)
4. [Training the Shadow Agent](#training-the-shadow-agent)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites
- API key (request from your administrator)
- Python 3.11+ or Node.js 20+ (for SDK usage)
- Basic understanding of task automation

### Quick Start

#### 1. Install the SDK

**Python:**
```bash
pip install murphy-client
```

**JavaScript:**
```bash
npm install murphy-client
```

#### 2. Initialize the Client

**Python:**
```python
from murphy_client import MurphyClient

client = MurphyClient(api_key="your-api-key")
```

**JavaScript:**
```javascript
const Murphy = require('murphy-client');
const client = new Murphy({ apiKey: 'your-api-key' });
```

#### 3. Execute Your First Task

**Python:**
```python
# Submit a task
result = client.tasks.execute(
    description="Create a blog post about AI",
    parameters={
        "topic": "Artificial Intelligence",
        "length": "medium",
        "style": "professional"
    }
)

print(f"Task ID: {result.task_id}")
print(f"Status: {result.status}")
```

**JavaScript:**
```javascript
// Submit a task
const result = await client.tasks.execute({
  description: "Create a blog post about AI",
  parameters: {
    topic: "Artificial Intelligence",
    length: "medium",
    style: "professional"
  }
});

console.log(`Task ID: ${result.taskId}`);
console.log(`Status: ${result.status}`);
```

---

## Core Concepts

### 1. Tasks
Tasks are units of work that Murphy executes. Each task has:
- **Type:** The category of work (e.g., content creation, data processing)
- **Parameters:** Input data and configuration
- **Status:** Current state (pending, executing, completed, failed)
- **Result:** Output data and metrics

### 2. Plans
Plans are collections of related tasks with dependencies:
- **Sequential:** Tasks execute one after another
- **Parallel:** Tasks execute simultaneously
- **Conditional:** Tasks execute based on conditions

### 3. Corrections
When Murphy makes a mistake, you can submit corrections:
- **Output Corrections:** Fix incorrect results
- **Process Corrections:** Improve how tasks are executed
- **Parameter Corrections:** Adjust input parameters

### 4. Shadow Agent
The Shadow Agent learns from your corrections:
- **Learns Patterns:** Identifies common correction patterns
- **Improves Accuracy:** Gets better over time
- **Provides Confidence:** Indicates certainty in decisions
- **Falls Back:** Uses Murphy Gate when uncertain

### 5. Murphy Gate
The deterministic validation system:
- **Validates Tasks:** Checks if tasks should proceed
- **Calculates Uncertainty:** Assesses risk levels
- **Provides Fallback:** Used when Shadow Agent is uncertain

---

## Using the System

### Creating and Executing Tasks

#### Method 1: Natural Language Description

```python
# Describe what you want in plain English
result = client.tasks.create_from_description(
    description="""
    Research the latest trends in AI for 2024,
    create a summary report, and email it to the team.
    """
)
```

#### Method 2: Structured Plan

```python
# Define a detailed plan
plan = {
    "name": "AI Research Report",
    "tasks": [
        {
            "name": "Research AI trends",
            "type": "research",
            "parameters": {
                "topic": "AI trends 2024",
                "sources": ["academic", "industry"]
            }
        },
        {
            "name": "Create summary",
            "type": "content_creation",
            "depends_on": ["Research AI trends"],
            "parameters": {
                "format": "report",
                "length": "2000 words"
            }
        },
        {
            "name": "Send email",
            "type": "communication",
            "depends_on": ["Create summary"],
            "parameters": {
                "recipients": ["team@company.com"],
                "subject": "AI Trends Report 2024"
            }
        }
    ]
}

result = client.plans.submit(plan)
```

### Monitoring Task Progress

```python
# Get task status
status = client.tasks.get_status(task_id)

print(f"Status: {status.status}")
print(f"Progress: {status.progress}%")
print(f"Estimated completion: {status.estimated_completion}")

# Wait for completion
result = client.tasks.wait_for_completion(
    task_id,
    timeout_seconds=300,
    poll_interval=5
)
```

### Handling Task Results

```python
# Get task result
result = client.tasks.get_result(task_id)

if result.status == "completed":
    print("Task completed successfully!")
    print(f"Output: {result.output}")
    print(f"Metrics: {result.metrics}")
elif result.status == "failed":
    print(f"Task failed: {result.error}")
```

---

## Submitting Corrections

### When to Submit Corrections

Submit corrections when:
- ✅ Output is incorrect or incomplete
- ✅ Process could be improved
- ✅ Parameters need adjustment
- ✅ Task took too long
- ✅ Resource usage was inefficient

### How to Submit Corrections

#### Output Correction

```python
# Correct an incorrect output
correction = client.corrections.submit(
    task_id=task_id,
    correction_type="output_modification",
    original_value="Incorrect output text",
    corrected_value="Correct output text",
    reason="The output had factual errors",
    severity="high"
)
```

#### Process Correction

```python
# Suggest process improvement
correction = client.corrections.submit(
    task_id=task_id,
    correction_type="process_improvement",
    suggestion="Use parallel processing for faster execution",
    reason="Task took too long to complete",
    severity="medium"
)
```

#### Parameter Correction

```python
# Correct parameters
correction = client.corrections.submit(
    task_id=task_id,
    correction_type="parameter_adjustment",
    parameter_name="temperature",
    original_value=0.9,
    corrected_value=0.7,
    reason="Output was too creative, needed more consistency",
    severity="low"
)
```

### Correction Best Practices

1. **Be Specific:** Clearly explain what was wrong and why
2. **Provide Context:** Include relevant information about the task
3. **Rate Severity:** Help prioritize important corrections
4. **Be Constructive:** Focus on improvement, not blame
5. **Submit Promptly:** Correct issues as soon as you notice them

---

## Training the Shadow Agent

### Understanding Training

The Shadow Agent learns from your corrections through:
1. **Pattern Recognition:** Identifies common correction patterns
2. **Feature Learning:** Understands what factors lead to errors
3. **Confidence Calibration:** Learns when to be certain vs. uncertain
4. **Continuous Improvement:** Gets better with more corrections

### Monitoring Training Progress

```python
# Get training statistics
stats = client.shadow_agent.get_stats()

print(f"Total corrections: {stats.total_corrections}")
print(f"Model accuracy: {stats.accuracy:.2%}")
print(f"Confidence: {stats.avg_confidence:.2%}")
print(f"Training data quality: {stats.data_quality_score:.2f}")
```

### Triggering Manual Training

```python
# Trigger training when you have enough corrections
training = client.shadow_agent.train(
    model_name="shadow_agent_v2",
    tune_hyperparameters=True,
    min_corrections=1000
)

print(f"Training started: {training.training_id}")
print(f"Estimated duration: {training.estimated_duration_minutes} minutes")

# Wait for training to complete
result = client.shadow_agent.wait_for_training(
    training.training_id,
    timeout_minutes=60
)

print(f"Training completed!")
print(f"New model accuracy: {result.accuracy:.2%}")
```

### Deploying Trained Models

```python
# Deploy with gradual rollout
deployment = client.shadow_agent.deploy(
    model_id=result.model_id,
    environment="production",
    use_gradual_rollout=True,
    initial_traffic=0.1  # Start with 10% traffic
)

print(f"Deployment started: {deployment.deployment_id}")
print(f"Initial traffic: {deployment.initial_traffic:.0%}")
```

---

## Best Practices

### 1. Task Design

**DO:**
- ✅ Break complex tasks into smaller subtasks
- ✅ Provide clear, specific descriptions
- ✅ Include relevant context and constraints
- ✅ Set realistic timeouts and resource limits

**DON'T:**
- ❌ Create overly complex single tasks
- ❌ Use vague or ambiguous descriptions
- ❌ Omit important context
- ❌ Set unrealistic expectations

### 2. Correction Submission

**DO:**
- ✅ Submit corrections promptly
- ✅ Provide detailed explanations
- ✅ Include examples when helpful
- ✅ Rate severity appropriately

**DON'T:**
- ❌ Delay correction submission
- ❌ Submit vague corrections
- ❌ Over-correct minor issues
- ❌ Submit duplicate corrections

### 3. Model Training

**DO:**
- ✅ Wait for sufficient corrections (1000+)
- ✅ Validate data quality before training
- ✅ Use gradual rollout for new models
- ✅ Monitor performance after deployment

**DON'T:**
- ❌ Train with insufficient data
- ❌ Deploy without testing
- ❌ Rush to 100% traffic
- ❌ Ignore performance metrics

### 4. Monitoring

**DO:**
- ✅ Check system status regularly
- ✅ Review performance metrics
- ✅ Respond to alerts promptly
- ✅ Track improvement over time

**DON'T:**
- ❌ Ignore alerts
- ❌ Skip regular reviews
- ❌ Neglect performance trends
- ❌ Overlook quality issues

---

## Troubleshooting

### Common Issues

#### Issue: Task Stuck in "Executing" State

**Solution:**
```python
# Check task status
status = client.tasks.get_status(task_id)

# If stuck for too long, cancel and retry
if status.duration_minutes > 60:
    client.tasks.cancel(task_id)
    # Resubmit with adjusted parameters
```

#### Issue: Low Shadow Agent Confidence

**Solution:**
- Submit more corrections for similar tasks
- Check if task type is well-represented in training data
- Consider using Murphy Gate fallback

#### Issue: Incorrect Results

**Solution:**
1. Submit a correction immediately
2. Review task parameters
3. Check if similar tasks have corrections
4. Consider retraining the model

#### Issue: Slow Performance

**Solution:**
- Check system status
- Review resource usage
- Consider breaking task into smaller parts
- Contact support if persistent

---

## Getting Help

### Resources
- **Documentation:** https://docs.murphy-system.com
- **API Reference:** https://api.murphy-system.com/docs
- **Community Forum:** https://community.murphy-system.com
- **Video Tutorials:** https://tutorials.murphy-system.com

### Support Channels
- **Email:** support@murphy-system.com
- **Chat:** Available in dashboard
- **Phone:** +1-XXX-XXX-XXXX (Business hours)

### Feedback
We value your feedback! Submit suggestions at:
- **Feature Requests:** https://feedback.murphy-system.com
- **Bug Reports:** https://bugs.murphy-system.com

---

## Next Steps

1. **Complete the Tutorial:** Follow our interactive tutorial in the dashboard
2. **Join the Community:** Connect with other users
3. **Explore Examples:** Check out example tasks and plans
4. **Start Small:** Begin with simple tasks and gradually increase complexity
5. **Provide Feedback:** Help us improve by submitting corrections

Welcome to Murphy System! We're excited to see what you'll build. 🚀