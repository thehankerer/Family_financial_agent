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
    
@tool     
def get_current_heart_rate(window_seconds: int = 10) -> Dict[str, Any]:
    """
    Fetch the most recent heart rate entries from DynamoDB within the last `window_seconds`
    and compute an average heart rate and stress level.

    Args:
        window_seconds (int): Time window (seconds) to consider as "current"

    Returns:
        Dict containing average BPM, confidence, stress level, and time range
    """
    if not dynamodb:
        return {"error": "DynamoDB not initialized"}

    try:
        table = dynamodb.Table("test_table")
        
        # Scan all items (for demo; in prod use a time-indexed query)
        response = table.scan()
        items = response.get("Items", [])

        if not items:
            return {"message": "No heart rate data found."}

        # Convert dateTime strings to datetime objects
        for entry in items:
            entry['dt_obj'] = datetime.strptime(entry['dateTime'], "%m/%d/%y %H:%M:%S")

        latest_time = max(entry['dt_obj'] for entry in items)
        recent_entries = [
            e for e in items if (latest_time - e['dt_obj']).total_seconds() <= window_seconds
        ]

        if not recent_entries:
            return {"message": f"No entries in the last {window_seconds} seconds."}

        avg_bpm = sum(float(e['value']['bpm']) for e in recent_entries) / len(recent_entries)
        avg_conf = sum(float(e['value']['confidence']) for e in recent_entries) / len(recent_entries)
    except Exception as e:
        return {"error": f"Error fetching data: {str(e)}"}
        

    
@tool
def calculate_stress_level(heart_rate: int) -> str:
    """Calculate stress level based on heart rate."""
    if heart_rate < 60:
        return "Low Stress"
    elif 60 <= heart_rate < 80:
        return "Moderate Stress"
    else:
        return "High Stress"
    


    
    
# --- Emotional Agent Setup ---
EMOTIONAL_SYSTEM_PROMPT = f'''
You are an empathetic personal assistant and part of a multi-agent system working
with the household_finance agent which helps make decisions for the user regarding 
their finances. You monitor the heart rate of the user and return the value. 
If the user is experiencing high stress levels, then you provide emotional support and encouragement based on the query given.'''


emotional_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)   
emotional_agent = Agent(
    model=emotional_model,
    system_prompt=EMOTIONAL_SYSTEM_PROMPT,
    tools=[get_current_heart_rate, calculate_stress_level ]
)       
# --- Demo / Initialization ---
def get_heart_rate(dateTime: str):
    """Fetch heart rate data using the emotional agent."""
    response = emotional_agent(f"Fetch heart rate data for {dateTime}")
    print("💓 Heart Rate Data:")
    print(response)
    return response 

'''

# Example usage
if __name__ == "__main__":  
    dateTime = "02/20/25 16:13:28"
    get_heart_rate(dateTime)
    print(datetime.now())
    
'''
    