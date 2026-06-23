# AutoGen Architecture Choice Agent

A simple AutoGen multi-agent setup designed to act as an "architecture-choice coach" for GenAI training scenarios. The agent helps users decide between single-agent, multi-agent, and various framework solutions like AutoGen, CrewAI, or LangGraph for a given problem.

## Architecture Overview

The system consists of two primary agents from the AutoGen library:

### 1. AssistantAgent: `architecture_choice_agent`

- **Role**: Core AI agent configured as an architecture-choice coach
- **LLM Provider**: Groq API
- **Model**: `llama-3.3-70b-versatile`
- **Purpose**: Explains decision cues, trade-offs, and suggests implementation shapes for GenAI solutions

### 2. UserProxyAgent: `learner`

- **Role**: User's proxy, initiates conversations with the `architecture_choice_agent`
- **Configuration**:
  - Runs in automated mode (`human_input_mode="NEVER"`)
  - No code execution (`code_execution_config=False`)
- **Responsibility**: Handles conversation termination when assistant responds with "TERMINATE"

---

## System Flow

```
User/Learner
    ↓ (Initiates Query)
UserProxyAgent ('learner')
    ↓ (Sends Query)
AssistantAgent ('architecture_choice_agent')
    ↓ (Queries LLM)
Groq LLM (llama-3.3-70b-versatile)
    ↓ (Generates Response)
AssistantAgent ('architecture_choice_agent')
    ↓ (Sends Response)
UserProxyAgent ('learner')
    ↓ (Displays to User)
User/Learner
```

### Data Flow Details

| Component | Direction | Message |
|-----------|-----------|---------|
| **UserProxyAgent** | → | Sends query to AssistantAgent |
| **AssistantAgent** | → | Queries Groq LLM with architecture question |
| **Groq LLM** | → | Returns generated response |
| **AssistantAgent** | → | Sends answer to UserProxyAgent |
| **Response** | Final | Agent's answer (ending with TERMINATE) |

---

## Key Characteristics

### Simplicity
- Only two agents: a user-facing proxy and a thinking assistant
- No orchestration complexity or coordination overhead
- Minimal configuration required

### Clear Termination Logic
- Built-in `TERMINATE` signal from AutoGen
- UserProxyAgent watches for this string and closes the loop automatically
- No custom stop logic needed

### Stateless Message Passing
- Each turn is self-contained
- Full conversation history included in each LLM call
- Ideal for architecture coaching (context matters)

### Automated Mode
- Runs without human intervention (`human_input_mode="NEVER"`)
- Suitable for demonstrations and training scenarios
- No code execution at the agent level

---

## Setup and Execution

### 1. Install Dependencies

```bash
pip install autogenstudio pyautogen
```

### 2. Configure Groq API Key

**Recommended approach** (Google Colab):
- Add `GROQ_API_KEY` to Colab's Secret Manager (click the 🔑 icon in the left sidebar)
- Set secret name: `GROQ_API_KEY`

**Alternative approaches**:
- Set as environment variable: `export GROQ_API_KEY=your_key_here`
- Add to `.env` file in your working directory

### 3. Run the Code

Execute the main Python script containing:
- Agent definition and configuration
- `run_demo_chat()` function call

---

## Example Usage

### Sample Query
```
learner (to architecture_choice_agent):

A hospital wants one system to read scan reports, check medication risk, 
schedule follow-up, and draft patient communication. Should this be 
single-agent or multi-agent, and why?
```

### Expected Response Structure

The assistant typically covers:

1. **Task Breakdown**
   - Identifies each subtask and its requirements
   - Analyzes complexity and specialization needs

2. **Single-Agent vs Multi-Agent Analysis**
   - **Multi-Agent Advantages**:
     - Modularity and focused development
     - Specialization per domain
     - Better scalability
     - Easier to adapt to changes
   - **Single-Agent Advantages**:
     - Simpler implementation
     - Tighter integration when tasks are interdependent

3. **Recommended Architecture**
   - Specific agent breakdown (e.g., 4 agents + orchestrator)
   - Data flow between agents
   - Integration points

4. **Decision Cues**
   - Complexity of tasks
   - Scalability requirements
   - Resource constraints
   - Future adaptation needs

5. **Trade-offs**
   - Multi-agent complexity vs. modularity benefits
   - Development/maintenance costs vs. long-term advantages

---

## Extension Opportunities

### Add More Agents
Replace the simple user proxy with a specialized agent system that can:
- Code and execute scaffolding examples
- Generate comparison matrices
- Produce architecture diagrams

### Enable Code Execution
Set `code_execution_config` to allow agents to:
- Build proof-of-concept implementations
- Generate boilerplate code
- Create architecture visualizations

### Multi-Turn Conversations
Modify system prompt to handle follow-up questions and iterative refinement of architecture decisions.

### Custom Termination
Replace "TERMINATE" with a more sophisticated conversation-end detector based on conversation state or satisfaction metrics.

---

## Message Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│ User Asks Architecture Question                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
        ┌──────────────────────┐
        │  UserProxyAgent      │
        │  ('learner')         │
        │  - Receives query    │
        │  - Forwards message  │
        └──────────┬───────────┘
                   │
                   ↓
        ┌──────────────────────────────────┐
        │ AssistantAgent                   │
        │ ('architecture_choice_agent')    │
        │ - Receives query                 │
        │ - Formats for LLM                │
        └──────────┬──────────────────────┘
                   │
                   ↓
        ┌──────────────────────────────────┐
        │ Groq LLM API Call                │
        │ Model: llama-3.3-70b-versatile   │
        │ - Analyzes architecture problem  │
        │ - Generates explanation          │
        │ - Adds TERMINATE signal          │
        └──────────┬──────────────────────┘
                   │
                   ↓
        ┌──────────────────────────────────┐
        │ AssistantAgent                   │
        │ - Receives LLM response          │
        │ - Formats for user               │
        └──────────┬──────────────────────┘
                   │
                   ↓
        ┌──────────────────────┐
        │  UserProxyAgent      │
        │  - Detects TERMINATE │
        │  - Closes conversation
        └──────────┬───────────┘
                   │
                   ↓
        ┌──────────────────────────────────┐
        │ User Receives Answer              │
        │ Conversation Complete             │
        └──────────────────────────────────┘
```

---

## Configuration Best Practices

### System Prompt Design
- Be specific about the coaching role
- Include examples of good single vs multi-agent decisions
- Define output format (structured analysis preferred)

### Groq API Considerations
- Fast inference for interactive demos
- Cost-effective for training scenarios
- Good quality for architectural analysis

### Error Handling
- Wrap API calls in try-catch blocks
- Handle network timeouts gracefully
- Log conversation history for debugging

---

## Common Use Cases

1. **Educational**: Teaching multi-agent systems design patterns
2. **Decision Support**: Helping teams choose architecture for real projects
3. **Proof of Concept**: Demonstrating AutoGen capabilities to stakeholders
4. **Workshop Material**: Live demos in training sessions
5. **Documentation**: Generating architecture decision rationale

---

## Limitations & Considerations

- **No Code Execution**: The system explains but doesn't implement
- **Single Turn Context**: Each query must be somewhat complete (no multi-turn refinement by default)
- **No Memory Between Sessions**: Each execution starts fresh
- **API Rate Limits**: Groq API has usage limits; monitor for production use
- **Hallucination Risk**: LLM may suggest architectures that don't exist

---

## Related Frameworks

For comparison or extension:
- **CrewAI**: More specialized agent roles with tools
- **LangGraph**: Lower-level control with state machines
- **AutoGen**: Best for rapid prototyping and automated debugging
- **Dify**: Visual workflow builder with agents

---

## Next Steps

1. **Run the demo** with sample architecture questions
2. **Customize the system prompt** for your domain
3. **Add code execution** to generate examples
4. **Extend with tools** (diagram generation, code scaffolding)
5. **Deploy as a service** for team use
