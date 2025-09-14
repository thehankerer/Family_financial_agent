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

# Load environment variables
load_dotenv()

# Initialize AWS clients globally
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
except Exception as e:
    print(f"Error initializing DynamoDB: {str(e)}")
    dynamodb = None

def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
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
                ':month': f"#{current_month}"
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
        total_allocated = sum(item.get('allocated_amount', 0) for item in budget_data)
        total_spent = sum(item.get('spent_amount', 0) for item in budget_data)
        total_remaining = sum(item.get('remaining_amount', 0) for item in budget_data)
        total_liquid_assets = sum(asset.get('current_value', 0) for asset in assets_data)
        
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
        total_liquid = sum(asset.get('current_value', 0) for asset in liquid_assets)
        
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
        
        # Identify reallocation opportunities
        reallocation_options = []
        for budget in budget_data:
            if budget.get('remaining_amount', 0) > 0:
                reallocation_options.append({
                    'category': budget.get('category', 'Unknown'),
                    'available': budget.get('remaining_amount', 0),
                    'impact': f"Reduces {budget.get('category', 'Unknown')} budget flexibility"
                })
        
        # Sort assets by liquidity
        asset_options = []
        for asset in assets_data:
            if asset.get('current_value', 0) >= required_amount * 0.1:  # At least 10% of required
                asset_options.append({
                    'asset_name': asset.get('asset_name', 'Unknown'),
                    'value': asset.get('current_value', 0),
                    'liquidity': asset.get('liquidity', 'Unknown'),
                    'impact': f"Reduces {asset.get('asset_type', 'Unknown')} reserves"
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
            monthly_allocation = goal.get('monthly_allocation', 0)
            target_amount = goal.get('target_amount', 0)
            current_amount = goal.get('current_amount', 0)
            
            months_to_target = 0
            if monthly_allocation > 0:
                remaining_amount = target_amount - current_amount
                months_to_target = remaining_amount / monthly_allocation
            
            # Calculate delay if expense reduces monthly allocation
            potential_delay = expense_amount / monthly_allocation if monthly_allocation > 0 else 0
            
            goal_impacts.append({
                'goal_name': goal.get('goal_name', 'Unknown'),
                'priority': goal.get('priority', 999),
                'current_progress': f"{current_amount}/{target_amount}",
                'months_to_completion': round(months_to_target, 1),
                'potential_delay_months': round(potential_delay, 1),
                'impact_severity': 'High' if potential_delay > 3 else 'Medium' if potential_delay > 1 else 'Low'
            })
        
        impact_analysis = {
            'expense_amount': expense_amount,
            'goal_impacts': sorted(goal_impacts, key=lambda x: x['priority']) if goal_impacts else [],
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

class FinanceAgent:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        guardrailArn = os.getenv('GUARDRAIL_ARN')
        guardrailId = os.getenv('GUARDRAIL_ID')
        guardrail_version = "DRAFT"
        
        # Enhanced model configuration
        # Temporarily disable guardrails for testing
        # Uncomment the guardrail lines below to re-enable them
        model = BedrockModel(
            model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            # guardrail_id=guardrailId,
            # guardrail_version=guardrail_version,
            # guardrail_trace="enabled"
        )

        self.financial_agent = Agent(
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
            Keep responses concise and actionable. Use clear formatting with bullet points and bold text for emphasis.
            
            **Analysis Summary:**
            [Brief overview of the financial decision]
            
            **Option 1: [Name]** (Recommended: X%)
            • Impact: [Key impacts]
            • Trade-offs: [What they give up]
            
            **Option 2: [Name]** (Recommended: Y%)
            • Impact: [Key impacts]
            • Trade-offs: [What they give up]
            
            **My Recommendation:** [Clear, actionable advice]
            
            --- What you avoid ---
            - Investment, loan, or insurance advice
            - Market speculation
            - Complex financial products
            - Stay within household budgeting scope
            
            --- Style ---
            - Conversational and friendly
            - Data-driven but not overwhelming
            - Focus on practical solutions
            - Encourage smart financial habits
            """,
            tools=[
                get_family_financial_overview,
                check_spending_capacity, 
                get_alternative_funding_sources,
                assess_goal_impact,
                calculate_budget
            ]
        )
    
    def process_query(self, query: str) -> str:
        """Process a financial query and return the agent's response as a string"""
        try:
            result = self.financial_agent(query)
            
            # Handle different possible return types from the Agent
            if result is None:
                return "I apologize, but I couldn't generate a response. Please try again."
            
            # If it's already a string, return it
            if isinstance(result, str):
                return result
            
            # Try different attributes that might contain the text
            if hasattr(result, 'content') and result.content:
                return str(result.content)
            elif hasattr(result, 'text') and result.text:
                return str(result.text)
            elif hasattr(result, 'output') and result.output:
                return str(result.output)
            elif hasattr(result, 'response') and result.response:
                return str(result.response)
            elif hasattr(result, 'messages') and result.messages:
                # If it has messages, get the last assistant message
                for msg in reversed(result.messages):
                    if hasattr(msg, 'content') and msg.content:
                        return str(msg.content)
                    elif hasattr(msg, 'text') and msg.text:
                        return str(msg.text)
                # If no content found in messages, try to convert the last message
                if result.messages:
                    return str(result.messages[-1])
            
            # Last resort: convert the entire object to string
            result_str = str(result)
            if result_str and result_str != "":
                return result_str
            else:
                return "I received your query but couldn't generate a proper response. Please try rephrasing your question."
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in process_query: {error_details}")  # Log for debugging
            return f"I encountered an error while processing your request: {str(e)}\n\nPlease try rephrasing your question or asking something else."

# Test the agent
if __name__ == "__main__":
    print("💰 Household Financial Decision Agent")
    print("=" * 50)
    
    agent = FinanceAgent()
    
    # Test query
    test_query = """
    Family ID: FAM003
    
    Query: Should we upgrade our phone plan for $100 more per month?
    """
    
    print("🔍 Processing query...")
    response = agent.financial_agent(test_query)
    print("\n📋 Agent Response:")
    print("-" * 30)
    print(response)