
# AutoGen Architecture Choice Agent

This project demonstrates a simple AutoGen multi-agent setup designed to act as an "architecture-choice coach" for GenAI training scenarios. The agent helps users decide between single-agent, multi-agent, and various framework solutions like AutoGen, CrewAI, or LangGraph for a given problem.

## Architecture Overview

The system consists of two primary agents from the AutoGen library:

1.  **`architecture_choice_agent` (AssistantAgent)**:
    *   This is the core AI agent, configured with a system message that defines its role as an architecture-choice coach.
    *   It uses the Groq API for its language model capabilities, specifically the `llama-3.3-70b-versatile` model by default.
    *   Its goal is to explain decision cues, trade-offs, and suggest simple implementation shapes for GenAI solutions.

2.  **`learner` (UserProxyAgent)**:
    *   This agent acts as the user's proxy, initiating conversations with the `architecture_choice_agent`.
    *   It is configured to run without human input mode for automated demonstrations (`human_input_mode="NEVER"`).
    *   It does not execute code (`code_execution_config=False`).
    *   It handles the termination of the conversation when the assistant agent responds with "TERMINATE".

### Simple Architecture Diagram

```mermaid
graph TD
    User[User/Learner] -->|Initiates Query| UserProxyAgent[UserProxyAgent: 'learner']
    UserProxyAgent -->|Sends Query| AssistantAgent[AssistantAgent: 'architecture_choice_agent']
    AssistantAgent -->|Queries LLM (Groq API)| GroqLLM[(Groq LLM: llama-3.3-70b-versatile)]
    GroqLLM -->|Generates Response| AssistantAgent
    AssistantAgent -->|Sends Response| UserProxyAgent
    UserProxyAgent -->|Displays to User| User

    subgraph Data Flow
        UserProxyAgent -.-> AssistantAgent: Task Message
        AssistantAgent -.-> GroqLLM: LLM Prompt
        GroqLLM -.-> AssistantAgent: LLM Response
        AssistantAgent -.-> UserProxyAgent: Agent's Answer (ending with TERMINATE)
    end

    style User fill:#f9f,stroke:#333,stroke-width:2px
    style UserProxyAgent fill:#bbf,stroke:#333,stroke-width:2px
    style AssistantAgent fill:#bbf,stroke:#333,stroke-width:2px
    style GroqLLM fill:#ccf,stroke:#333,stroke-width:2px
```

## Setup and Execution

To run this agent, you need to:

1.  **Install Dependencies**: Make sure AutoGen and related packages are installed:
    ```bash
    !pip install autogenstudio pyautogen
    ```

2.  **Set up Groq API Key**: Provide your `GROQ_API_KEY`.
    *   **Recommended**: Add `GROQ_API_KEY` to Google Colab's Secret Manager (the '🔑' icon in the left sidebar) with the name `GROQ_API_KEY`.
    *   Alternatively, you can set it as an environment variable or in a `.env` file in your working directory.

3.  **Run the Code**: Execute the main Python script (or the Colab cell containing the agent definition and `run_demo_chat()` call).

## Demonstration Output

Below is the output from a sample run of the `run_demo_chat()` function, where the `learner` agent asks the `architecture_choice_agent` about a hospital system design:

```
learner (to architecture_choice_agent):

A hospital wants one system to read scan reports, check medication risk, schedule follow-up, and draft patient communication. Should this be single-agent or multi-agent, and why?

--------------------------------------------------------------------------------
architecture_choice_agent (to learner):

To determine whether a single-agent or multi-agent system is more suitable for the hospital's needs, let's break down the tasks involved:

1.  **Reading scan reports**: This task requires natural language processing (NLP) capabilities to extract relevant information from the reports.
2.  **Checking medication risk**: This task involves analyzing patient data, medication lists, and potential interactions, which can be complex and require specialized knowledge.
3.  **Scheduling follow-up**: This task requires integration with the hospital's scheduling system and consideration of factors like patient availability, doctor schedules, and resource allocation.
4.  **Drafting patient communication**: This task involves generating clear, concise, and empathetic messages to patients, which requires NLP and understanding of patient needs.

Considering these tasks, a **multi-agent system** might be more suitable for several reasons:

*   **Modularity**: Each task can be handled by a separate agent, allowing for more focused development, maintenance, and updates. This modularity also enables easier integration of new agents or replacement of existing ones if needed.
*   **Specialization**: Different agents can be specialized in specific domains (e.g., NLP for report reading, pharmacology for medication risk assessment), leading to more accurate and effective processing.
*   **Scalability**: A multi-agent system can be more scalable, as each agent can be designed to handle a specific workload, and additional agents can be added as needed to handle increased demand.
*   **Flexibility**: With a multi-agent system, the hospital can more easily adapt to changing requirements or integrate new technologies, as each agent can be modified or replaced independently.

However, a **single-agent system** might be considered if:

*   **Simple implementation**: The hospital has limited resources or prefers a simpler implementation, and the tasks are relatively straightforward.
*   **Tight integration**: The tasks are highly interdependent, and a single agent can effectively handle all aspects without significant performance degradation.

In terms of implementation shape, a multi-agent system for the hospital might involve:

*   **Agent 1**: NLP-based report reader, extracting relevant information from scan reports.
*   **Agent 2**: Medication risk assessment agent, analyzing patient data and medication lists.
*   **Agent 3**: Scheduling agent, integrating with the hospital's scheduling system to arrange follow-ups.
*   **Agent 4**: Patient communication agent, generating draft messages to patients based on the output from the other agents.
*   **Orchestrator**: A central component that coordinates the interactions between agents, ensuring seamless data exchange and workflow execution.

Decision cues to consider:

*   Complexity of tasks and required specializations
*   Scalability and flexibility needs
*   Available resources (development, maintenance, integration)
*   Potential for future adaptations or integrations

Trade-offs to weigh:

*   Increased complexity in a multi-agent system vs. potential benefits of modularity and specialization
*   Higher development and maintenance costs for a multi-agent system vs. potential long-term advantages

TERMINATE
```

