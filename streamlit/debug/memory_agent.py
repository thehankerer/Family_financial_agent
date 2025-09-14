import os
import logging
from dotenv import load_dotenv

from strands import Agent
from strands_tools import mem0_memory, use_llm
from strands.models import BedrockModel

logger = logging.getLogger(__name__)
load_dotenv()

# --- User & AWS setup ---
USER_ID = "mem0_user"


# --- System prompt ---
MEMORY_SYSTEM_PROMPT = f"""
You are a personal finance memory assistant that helps a multi-agent system by storing and retrieving family financial data.

Capabilities:
- Store detailed outputs from the Household_agent (action="store")
- Summarize user/family financial decision-making preferences
- Retrieve relevant past financial decisions and summaries (action="retrieve")
- List all stored decisions and summaries for auditing (action="list")
- Provide concise, structured responses suitable for other agents

Key Rules:
- Always include user_id={USER_ID} in tool calls
- Be conversational but focus on structured financial information
- Format stored data clearly with both:
    1. Full Household_agent output
    2. Summarized preference profile
- Acknowledge that information has been stored
- Only return information relevant to the current query
- Indicate politely when information is unavailable
- Do not provide financial advice yourself; only store, summarize, and recall
"""

# --- Bedrock Model Setup ---
memory_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    # or inference_profile_arn=MEMORY_PROFILE_ARN  # uncomment if using profile instead
)

os.environ["MEM0_LLM_MODEL"] = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

# --- Memory Agent ---
memory_agent = Agent(
    model=memory_model,
    system_prompt=MEMORY_SYSTEM_PROMPT,
    tools=[mem0_memory, use_llm]
)

# --- Demo / Initialization ---
def initialize_user_preferences():
    """Store initial user preferences using mem0_memory."""
    content = """My name is Charlie. I prefer a monthly budget of 40% fixed expenses, 30% wants, 30% savings.
I plan a trip to South Korea next spring and want $4000 saved over 12 months for it.
I enjoy visiting new restaurants and looking for discounts."""
    
    # Correct way to store memory directly
    #memory_agent(f"store: {content}")  # the agent knows how to interpret store commands
    memory_agent.tool.mem0_memory(action="store", content=content, user_id=USER_ID, model = memory_model)
    
    print("✅ User preferences for Charlie initialized!")
    

# --- Interactive Loop ---
if __name__ == "__main__":
    print("💾 Personal Finance Memory Agent")
    print("=" * 50)
    print("Commands: 'demo' to initialize, 'exit' to quit")

    while True:
        try:
            user_input = input("\n> ")

            if user_input.lower() in ["exit", "quit"]:
                print("\nGoodbye! 👋")
                break
            elif user_input.lower() == "demo":
                initialize_user_preferences()
                continue
            elif user_input.lower() == "list memories":
                # Example: list all stored memories
                memories = mem0_memory(action="list", user_id=USER_ID)
                print("\n📋 All stored memories:")
                print("-" * 30)
                for m in memories:
                    print(m)
                continue
            elif user_input.lower().startswith("retrieve"):
                # Example: retrieve based on query
                query_text = user_input[len("retrieve"):].strip()
                memories = mem0_memory(action="retrieve", query=query_text, user_id=USER_ID)
                print("\n📋 Retrieved memories:")
                print("-" * 30)
                for m in memories:
                    print(m)
                continue

            # Otherwise, let the agent summarize or interact
            response = memory_agent(user_input)
            print("\n📋 Agent Response:")
            print("-" * 30)
            print(response)

        except KeyboardInterrupt:
            print("\n\nExecution interrupted. Exiting...")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {str(e)}")
