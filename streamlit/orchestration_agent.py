import logging
from strands import Agent
from strands_tools import use_llm
from strands.models import BedrockModel

# Import your Finance & Memory agents
from memory_agentsimple import memory_agentnew, local_memory   # ✅ import both
from household_agent import financial_agent

logger = logging.getLogger(__name__)

# --- Constants ---
USER_ID = "household_demo_user"  # You can make this dynamic if needed

# --- Orchestration Agent System Prompt ---
ORCHESTRATION_PROMPT = """
You are the Orchestration Agent in a household finance multi-agent system.
You coordinate between two specialized agents:

1. Finance Agent:
   - Analyzes budgets, goals, trade-offs, and alternatives.
   - Gives structured outputs about financial decisions.

2. Memory Agent:
   - Stores and retrieves past financial decisions and preferences.
   - Never gives advice; only recalls, summarizes, or lists decisions.

Core Rules:
- Route queries naturally without user commands like 'store' or 'retrieve'.
- When routing to Finance Agent:
   1. First retrieve relevant memories from Memory Agent.
   2. Pass those memories along with the user query to Finance Agent for context.
   3. After Finance Agent responds, summarize the decision and store it in Memory Agent.
- Always be clear where information came from (📊 Finance, 💾 Memory).
- Keep responses structured, concise, and demo-ready with sections and icons.
"""

orchestration_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)

orchestration_agent = Agent(
    model=orchestration_model,
    system_prompt=ORCHESTRATION_PROMPT,
    tools=[use_llm]   # ✅ only LLM tools, memory handled manually
)

# --- Orchestration Logic ---
def handle_user_query(user_input: str):
    """
    Main orchestration logic.
    Routes queries, enriches with memory, and stores finance decisions automatically.
    """

    # Step 1: Check if user explicitly asks for memory (debug/demo mode)
    if user_input.lower().startswith("list memories"):
        memories = local_memory(action="list", user_id=USER_ID)
        return "💾 Past memories:\n" + "\n".join(memories)

    if user_input.lower().startswith("retrieve"):
        query = user_input[len("retrieve"):].strip()
        memories = local_memory(action="retrieve", query=query, user_id=USER_ID)
        return "💾 Retrieved memories:\n" + "\n".join(memories)

    # Step 2: Retrieve relevant past decisions for context
    past_memories = local_memory(action="retrieve", query=user_input, user_id=USER_ID)

    finance_prompt = f"""
📖 Relevant Past Decisions:
{past_memories if past_memories else "None found."}

💬 User Query:
{user_input}
    """

    # Step 3: Send enriched query to Finance Agent
    finance_response = financial_agent(finance_prompt)

    # Step 4: Summarize and store decision in Memory Agent
    summary_content = f"""
Decision for query: "{user_input}"
Finance Agent Output (short summary): {finance_response[:500]}...
    """.strip()

    mem0_memory(action="store", content=summary_content, user_id=USER_ID)

    # Step 5: Return structured final response
    return f"""
📊 Finance Agent Response
---------------------------
{finance_response}

💾 Memory Updated
------------------
This decision was summarized and stored for future recommendations.
    """

# --- Run Demo Loop ---
if __name__ == "__main__":
    print("🤖 Household Orchestration Agent Ready")
    print("=" * 60)

    while True:
        user_input = input("\n💬 Enter your query (or 'exit' to quit): ")
        if user_input.lower() in ["exit", "quit"]:
            break
        response = handle_user_query(user_input)
        print(response)
