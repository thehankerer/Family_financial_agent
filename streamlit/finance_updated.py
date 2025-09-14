from strands import Agent, tool
from strands_tools import calculator, current_time
from strands.models import BedrockModel
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import boto3
from decimal import Decimal
from typing import Dict, List, Any

# Load environment variables from .env file
load_dotenv()

# Access the environment variables
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
#guardrailId = os.getenv('GUARDRAIL_ID')
guardrailArn = os.getenv('GUARDRAIL_ARN')
guardrailId = os.getenv('GUARDRAIL_ID')
guardrail_version = "DRAFT"

bedrock_runtime = boto3.client('bedrock-runtime')

# Initialize DynamoDB client with debug info
try:
    print(f"DEBUG: Initializing DynamoDB with region: {AWS_REGION}")
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    print("DEBUG: DynamoDB client initialized successfully")
    
    # Test connection
    client = boto3.client(
        'dynamodb',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    tables = client.list_tables()
    print(f"DEBUG: Available tables: {tables['TableNames']}")
    
except Exception as e:
    print(f"DEBUG: Error initializing DynamoDB: {str(e)}")
    import traceback
    print(f"DEBUG: Full traceback: {traceback.format_exc()}")
    dynamodb = None
    
#initialise AWS clients
#bedrock_client = boto3.client('bedrock')
#bedrock_runtime = boto3.client('bedrock-runtime')

# Helper function to convert Decimal to float for JSON serialization
def decimal_to_float(obj):
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj

@tool
def get_family_financial_overview(family_id: str) -> str:
    """Get comprehensive financial overview for a family from DynamoDB."""
    try:
        # Get family profile
        family_table = dynamodb.Table('FamilyProfiles')
        family_response = family_table.get_item(Key={'family_id': family_id})
        
        if 'Item' not in family_response:
            return f"❌ Family {family_id} not found in database"
        
        family_data = decimal_to_float(family_response['Item'])
        
        # Get current budget allocations
        budget_table = dynamodb.Table('BudgetAllocations')
        current_month = datetime.now().strftime('%Y-%m')
        budget_response = budget_table.query(
            KeyConditionExpression='family_id = :fid AND begins_with(category_month, :month)',
            ExpressionAttributeValues={
                ':fid': family_id,
                ':month': f"#{current_month}"  # This will get all categories for current month
            }
        )
        
        # Get financial goals
        goals_table = dynamodb.Table('FinancialGoals')
        goals_response = goals_table.query(
            KeyConditionExpression='family_id = :fid',
            ExpressionAttributeValues={':fid': family_id}
        )
        
        # Get liquid assets
        assets_table = dynamodb.Table('FamilyAssets')
        assets_response = assets_table.query(
            KeyConditionExpression='family_id = :fid',
            FilterExpression='liquidity = :liq',
            ExpressionAttributeValues={
                ':fid': family_id,
                ':liq': 'High'
            }
        )
        
        budget_data = decimal_to_float(budget_response.get('Items', []))
        goals_data = decimal_to_float(goals_response.get('Items', []))
        assets_data = decimal_to_float(assets_response.get('Items', []))
        
        # Calculate totals
        total_allocated = sum(item['allocated_amount'] for item in budget_data)
        total_spent = sum(item['spent_amount'] for item in budget_data)
        total_remaining = sum(item['remaining_amount'] for item in budget_data)
        total_liquid_assets = sum(asset['current_value'] for asset in assets_data)
        
        overview = {
            'family_info': family_data,
            'monthly_budget': {
                'total_allocated': total_allocated,
                'total_spent': total_spent,
                'total_remaining': total_remaining,
                'categories': budget_data
            },
            'financial_goals': goals_data,
            'liquid_assets': {
                'total': total_liquid_assets,
                'accounts': assets_data
            }
        }
        
        return f"📊 Financial Overview for {family_data['family_name']}:\n" + json.dumps(overview, indent=2)
        
    except Exception as e:
        return f"❌ Error retrieving family data: {str(e)}"

@tool
def check_spending_capacity(family_id: str, amount: float, category: str) -> str:
    """Check if family can afford a specific expense in a category."""
    try:
        current_month = datetime.now().strftime('%Y-%m')
        
        # Get current budget for the category
        budget_table = dynamodb.Table('BudgetAllocations')
        budget_key = f"{category}#{current_month}"
        
        budget_response = budget_table.get_item(
            Key={
                'family_id': family_id,
                'category_month': budget_key
            }
        )
        
        # Get liquid assets
        assets_table = dynamodb.Table('FamilyAssets')
        assets_response = assets_table.query(
            KeyConditionExpression='family_id = :fid',
            FilterExpression='liquidity = :liq',
            ExpressionAttributeValues={
                ':fid': family_id,
                ':liq': 'High'
            }
        )
        
        budget_item = decimal_to_float(budget_response.get('Item', {}))
        liquid_assets = decimal_to_float(assets_response.get('Items', []))
        total_liquid = sum(asset['current_value'] for asset in liquid_assets)
        
        analysis = {
            'requested_amount': amount,
            'category': category,
            'current_budget': budget_item,
            'budget_remaining': budget_item.get('remaining_amount', 0),
            'budget_shortfall': max(0, amount - budget_item.get('remaining_amount', 0)),
            'liquid_assets_available': total_liquid,
            'can_afford_from_budget': amount <= budget_item.get('remaining_amount', 0),
            'can_afford_with_assets': amount <= (budget_item.get('remaining_amount', 0) + total_liquid)
        }
        
        return f"💵 Spending Capacity Analysis:\n" + json.dumps(analysis, indent=2)
        
    except Exception as e:
        return f"❌ Error checking spending capacity: {str(e)}"

@tool
def get_alternative_funding_sources(family_id: str, required_amount: float) -> str:
    """Find alternative ways to fund an expense (budget reallocation, asset liquidation)."""
    try:
        current_month = datetime.now().strftime('%Y-%m')
        
        # Get all current budget allocations
        budget_table = dynamodb.Table('BudgetAllocations')
        budget_response = budget_table.query(
            KeyConditionExpression='family_id = :fid',
            FilterExpression='contains(category_month, :month)',
            ExpressionAttributeValues={
                ':fid': family_id,
                ':month': current_month
            }
        )
        
        # Get all assets by liquidity
        assets_table = dynamodb.Table('FamilyAssets')
        assets_response = assets_table.query(
            KeyConditionExpression='family_id = :fid',
            ExpressionAttributeValues={':fid': family_id}
        )
        
        budget_data = decimal_to_float(budget_response.get('Items', []))
        assets_data = decimal_to_float(assets_response.get('Items', []))
        
        # Identify reallocation opportunities (categories with remaining budget)
        reallocation_options = []
        for budget in budget_data:
            if budget['remaining_amount'] > 0:
                reallocation_options.append({
                    'category': budget['category'],
                    'available': budget['remaining_amount'],
                    'impact': f"Reduces {budget['category']} budget flexibility"
                })
        
        # Sort assets by liquidity
        asset_options = []
        for asset in assets_data:
            if asset['current_value'] >= required_amount:
                asset_options.append({
                    'asset_name': asset['asset_name'],
                    'value': asset['current_value'],
                    'liquidity': asset['liquidity'],
                    'impact': f"Reduces {asset['asset_type']} reserves"
                })
        
        alternatives = {
            'required_amount': required_amount,
            'budget_reallocation': reallocation_options,
            'asset_liquidation': asset_options,
            'total_available_budget': sum(opt['available'] for opt in reallocation_options),
            'recommendations': []
        }
        
        return f"🔄 Alternative Funding Sources:\n" + json.dumps(alternatives, indent=2)
        
    except Exception as e:
        return f"❌ Error finding alternatives: {str(e)}"

@tool 
def assess_goal_impact(family_id: str, expense_amount: float) -> str:
    """Assess how an expense will impact family financial goals."""
    try:
        # Get all active financial goals
        goals_table = dynamodb.Table('FinancialGoals')
        goals_response = goals_table.query(
            KeyConditionExpression='family_id = :fid',
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':fid': family_id,
                ':status': 'Active'
            }
        )
        
        goals_data = decimal_to_float(goals_response.get('Items', []))
        
        # Calculate impact on each goal
        goal_impacts = []
        for goal in goals_data:
            months_to_target = 0
            if goal['monthly_allocation'] > 0:
                remaining_amount = goal['target_amount'] - goal['current_amount']
                months_to_target = remaining_amount / goal['monthly_allocation']
            
            # Calculate delay if expense reduces monthly allocation
            potential_delay = expense_amount / goal['monthly_allocation'] if goal['monthly_allocation'] > 0 else 0
            
            goal_impacts.append({
                'goal_name': goal['goal_name'],
                'priority': goal['priority'],
                'current_progress': f"{goal['current_amount']}/{goal['target_amount']}",
                'months_to_completion': round(months_to_target, 1),
                'potential_delay_months': round(potential_delay, 1),
                'impact_severity': 'High' if potential_delay > 3 else 'Medium' if potential_delay > 1 else 'Low'
            })
        
        impact_analysis = {
            'expense_amount': expense_amount,
            'goal_impacts': sorted(goal_impacts, key=lambda x: x['priority']),
            'highest_priority_affected': min(goal_impacts, key=lambda x: x['priority']) if goal_impacts else None
        }
        
        return f"🎯 Goal Impact Analysis:\n" + json.dumps(impact_analysis, indent=2)
        
    except Exception as e:
        return f"❌ Error assessing goal impact: {str(e)}"

@tool
def calculate_budget(monthly_income: float) -> str:
    """Calculate 50/30/20 budget breakdown."""
    needs = monthly_income * 0.50
    wants = monthly_income * 0.30  
    savings = monthly_income * 0.20
    return f"💰 Budget for ${monthly_income:,.0f}/month:\n• Needs: ${needs:,.0f} (50%)\n• Wants: ${wants:,.0f} (30%)\n• Savings: ${savings:,.0f} (20%)"






# Enhanced model configuration
model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    guardrail_id = guardrailId,
    guardrail_version = guardrail_version,
    guardrail_trace = "enabled"
)

FinanceAgent = Agent(
    model=model,
    system_prompt=""" 
    You are a Household Financial Decision Agent with access to real-time family financial data from DynamoDB.
    
    --- Your Enhanced Capabilities ---
    1. Access complete family financial profiles including:
       - Monthly income and budget allocations
       - Current spending across categories
       - Financial goals with priorities and timelines
       - Asset liquidity and availability
       - Historical decision patterns
    
    2. For any spending query:
       - Use get_family_financial_overview() to understand the family's complete situation
       - Use check_spending_capacity() to analyze if they can afford the expense
       - Use get_alternative_funding_sources() to find reallocation options
       - Use assess_goal_impact() to understand effects on long-term goals
       - Provide 2-3 realistic alternatives with detailed impact analysis
    
    --- Decision Framework ---
    For each alternative, provide:
    • Alternative title and description
    • Specific budget categories affected
    • Impact on financial goals (delays, progress disruption)
    • Asset usage requirements
    • Preference score (0-100%) based on:
      - Goal alignment (40%)
      - Budget health (30%) 
      - Liquidity impact (20%)
      - Family risk tolerance (10%)
    
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
    """,
    tools=[
        get_family_financial_overview,
        check_spending_capacity, 
        get_alternative_funding_sources,
        assess_goal_impact,
        calculate_budget
    ]
)

# --- Test the Enhanced Agent ---
if __name__ == "__main__":
    print("💰 Enhanced Household Financial Decision Agent")
    print("=" * 50)
    
    # Test query using our sample data
    test_query = """
    Family ID: FAM003
    
    Query: My spouse suggests upgrading our family phone plan to a premium package 
    that costs $100 more per month. Should we make this change?
    """
    
    print("🔍 Processing query...")
    test_query_2 = "What stocks should I invest in to be able to afford a new car?"
    response = financial_agent(test_query)
    print(response)
    print("\n📋 Agent Response:")
    print("-" * 30)
    print(response)

    while True:
        user_input = input("\n💬 Enter another query (or 'exit' to quit): ")
        if user_input.lower() in ['exit', 'quit']:
            break
        response = financial_agent(user_input)
        print("\n📋 Agent Response:")
        print("-" * 30)
        print(response)
        