# memory_agent.py
import os
import json
from dotenv import load_dotenv
from strands import Agent
from strands_tools import use_agent
from strands.models import BedrockModel

load_dotenv()

USER_ID = "mem0_user"
MEMORY_FILE = "memory_store.json"

def load_memories():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_memories(memories):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, indent=2)

def local_memory_old(action, user_id, content=None, query=None):
    """Custom JSON memory tool."""
    memories = load_memories()

    if action == "store":
        memories.append({"user_id": user_id, "content": content})
        save_memories(memories)
        return f"✅ Stored memory for {user_id}"

    elif action == "list":
        return [m for m in memories if m["user_id"] == user_id]

    elif action == "retrieve":
        return [
            m for m in memories
            if m["user_id"] == user_id and query.lower() in m["content"].lower()
        ]

    return "❌ Unknown action"

def local_memory(action: str, content: str = None, query: str = None, user_id: str = "default_user", status: str = "tentative"):
    """JSON file-backed memory system with tentative/confirmed status."""
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w") as f:
            json.dump({}, f, indent=2)

    with open(MEMORY_FILE, "r") as f:
        data = json.load(f)

    user_memories = data.get(user_id, [])

    if action == "store" and content:
        # Add timestamp and status
        entry = {
            "content": content,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        user_memories.append(entry)
        data[user_id] = user_memories
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return f"✅ Stored memory ({status}) for {user_id}"

    elif action == "confirm" and query:
        # Confirm all tentative entries containing the query
        for entry in user_memories:
            if query.lower() in entry["content"].lower() and entry["status"] == "tentative":
                entry["status"] = "confirmed"
        data[user_id] = user_memories
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return f"✅ Confirmed matching entries for {user_id}"

    elif action == "retrieve" and query:
        # Return both tentative and confirmed, optionally filter by status
        return [m["content"] for m in user_memories if query.lower() in m["content"].lower()]

    elif action == "list":
        return [f"{m['timestamp']} | {m['status']} | {m['content']}" for m in user_memories]

    return []

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


memory_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)

memory_agentnew = Agent(
    model=memory_model,
    system_prompt=MEMORY_SYSTEM_PROMPT,
    tools=[local_memory, use_agent]
)
