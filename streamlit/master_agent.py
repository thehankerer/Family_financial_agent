from strands import Agent, tool

from strands.models import BedrockModel
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
from emotional_agent import emotional_agent
from household_agent import financial_agent


load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    
)

system_prompt = f"""
You are the Master Agent coordinating between the Financial Decision Agent and the emotional agent. 
Your streamlined workflow:
1. Only if you recieve user queries related to household finance, you will direct them to the Financial Decision Agent along with the Family ID so that the agent can access the financial data and make full use of its own tools. 
2. If the user query is emotional or non-financial, direct it to the Emotional Agent.
3. Do not change the financial decision agent's response and give the full insights so that the user can read.
4. After the Financial Decision Agent's response provide any emotional insights from the emotional agent to provide a final, empathetic reply to the user. If the user is not that stressed also, react by saying they are doing great.


Key Rules:
- Always prioritize user well-being and emotional state.
- Never modify the output of the finacial decision agent.
- Ensure clarity on which agent provided which part of the information.
- The emotional agent can access the heart rate data from the test_table table in DynamoDB.Use that data to provide insights on the user's stress levels. 
- Always be clear where information came from (📊 Finance, Emotional).

The financial agent must provide output in this way
--- Enhanced Output Format ---
    **Family Financial Status:** [Brief overview]
    
    **Analysis for [Expense Request]:**
    
    1. **[Alternative 1 Name]** (Preference: X%)
       - Budget Impact: [Specific categories and amounts]
       - Goal Impact: [Which goals affected, timeline changes]
       - Liquidity: [Asset usage required]
       - Risk Level: [Low/Medium/High]
    
    2. **[Alternative 2 Name]** (Preference: Y%)
       - [Same format]
    
    3. **[Alternative 3 Name]** (Preference: Z%)
       - [Same format]
    
    **Recommendation:** [Top choice with reasoning]
    
    --- What you avoid ---
    - Investment, loan, or insurance advice
    - Market speculation
    - Stay within household budgeting scope
    
    --- Style ---
    - Data-driven and specific (use actual numbers from DB)
    - Family-oriented and supportive
    - Clear trade-off explanations
    - Actionable recommendations
    
The emotional agent can provide emotional support and encouragement based on the user's stress level.

Available specialised agents:
- Financial Decision Agent: Expert in household financial decisions, budgeting, and expense management. Provides which financial options are best suited for the user's needs, and their respective outcomes.
- Emotional Agent: Monitors user's emotional state through heart rate data, provides stress level insights, and suggests emotional support when needed.

"""

MasterAgent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=[financial_agent, emotional_agent])

if __name__ == "__main__":
    print("Multi agent system: Master Agent coordinating Financial and Emotional Agents")
    print("=" * 50)
    
    # Test query using our sample data
    test_query = """
    Family ID: FAM003
    
    Query: My spouse suggests upgrading our family phone plan to a premium package 
    that costs $100 more per month. Should we make this change?
    """
    test_query_2 = """
    Family ID: FAM003
    
    Query: Do you know if I'm stressed right now?
    """
    print("🔍 Processing query...")
    #test_query_2 = "What stocks should I invest in to be able to afford a new car?"
    response = master_agent(test_query)
    print(response)
    #print("\n📋 Agent Response:")
    #print("-" * 30)
    #print(response)
    while True:
        user_input = input("\n💬 Enter another query (or 'exit' to quit): ")
        if user_input.lower() in ['exit', 'quit']:
            break
        response = financial_agent(user_input)
        print("\n📋 Agent Response:")
        print("-" * 30)
        print(response)
        