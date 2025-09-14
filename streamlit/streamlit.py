import streamlit as st
import boto3
import uuid
from datetime import datetime, date
from decimal import Decimal
import time
import hashlib
import pandas as pd

st.set_page_config(
    page_title="Family Finance Assistant",
    layout="wide"
)

@st.cache_resource
def init_dynamodb():
    return boto3.resource('dynamodb', region_name='us-east-1')

def convert_floats(obj):
    if isinstance(obj, list):
        return [convert_floats(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against provided password"""
    return stored_password == hash_password(provided_password)

def authenticate_user(email, password):
    """Authenticate user against DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('FamilyProfiles')
        
        response = table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={
                ':email': email
            }
        )
        
        if response['Items'] and len(response['Items']) > 0:
            user_data = response['Items'][0]
            if 'password' in user_data:
                if len(user_data['password']) == 64:
                    if verify_password(user_data['password'], password):
                        return True, user_data
                else:
                    if user_data['password'] == password:
                        update_password_hash(user_data['family_id'], password)
                        return True, user_data
            return False, "Invalid password"
        else:
            return False, "Email not found"
            
    except Exception as e:
        return False, f"Authentication error: {str(e)}"

def update_password_hash(family_id, password):
    """Update password to hashed version"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('FamilyProfiles')
        table.update_item(
            Key={'family_id': family_id},
            UpdateExpression='SET password = :password, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':password': hash_password(password),
                ':updated_at': datetime.utcnow().isoformat() + "Z"
            }
        )
    except Exception as e:
        st.error(f"Error updating password: {str(e)}")

def save_family_to_dynamodb(family_data):
    """Save family profile to DynamoDB FamilyProfiles table"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('FamilyProfiles')
        family_id = f"FAM{str(uuid.uuid4())[:6].upper()}"
        current_time = datetime.utcnow().isoformat() + "Z"
        
        item = {
            "family_id": family_id,
            "family_name": family_data["family_name"],
            "total_monthly_income": family_data["total_monthly_income"],
            "family_size": family_data["family_size"],
            "location": family_data["location"],
            "risk_tolerance": family_data["risk_tolerance"],
            "created_at": current_time,
            "updated_at": current_time,
            "email": family_data["email"],
            "password": hash_password(family_data["password"])
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True, family_id
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return False, None

# Data management functions
def save_budget_allocation(family_id, category, year_month, allocated_amount, spent_amount=0):
    """Save budget allocation to DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('BudgetAllocations')
        
        item = {
            "family_id": family_id,
            "category_month": f"{category}#{year_month}",
            "category": category,
            "allocated_amount": allocated_amount,
            "spent_amount": spent_amount,
            "remaining_amount": allocated_amount - spent_amount,
            "year_month": year_month
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True
    except Exception as e:
        st.error(f"Error saving budget allocation: {str(e)}")
        return False

def save_expense_transaction(family_id, amount, category, subcategory, description, family_member, necessity_level, transaction_date):
    """Save expense transaction to DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('ExpenseTransactions')
        
        transaction_id = f"TXN{str(uuid.uuid4())[:6].upper()}"
        
        item = {
            "family_id": family_id,
            "transaction_date_id": f"{transaction_date}#{transaction_id}",
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
            "description": description,
            "family_member": family_member,
            "necessity_level": necessity_level,
            "transaction_date": str(transaction_date)
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True
    except Exception as e:
        st.error(f"Error saving expense transaction: {str(e)}")
        return False

def save_family_asset(family_id, asset_name, asset_type, current_value, liquidity):
    """Save family asset to DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('FamilyAssets')
        
        asset_id = f"{asset_type.upper()[:3]}{str(uuid.uuid4())[:6].upper()}"
        
        item = {
            "family_id": family_id,
            "asset_type_id": f"{asset_type}#{asset_id}",
            "asset_name": asset_name,
            "asset_type": asset_type,
            "current_value": current_value,
            "liquidity": liquidity,
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True
    except Exception as e:
        st.error(f"Error saving family asset: {str(e)}")
        return False

def save_financial_goal(family_id, goal_name, target_amount, current_amount, target_date, priority, monthly_allocation):
    """Save financial goal to DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('FinancialGoals')
        
        goal_id = f"GOAL{str(uuid.uuid4())[:6].upper()}"
        
        item = {
            "family_id": family_id,
            "goal_id": goal_id,
            "goal_name": goal_name,
            "target_amount": target_amount,
            "current_amount": current_amount,
            "target_date": str(target_date),
            "priority": priority,
            "monthly_allocation": monthly_allocation,
            "status": "Active"
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True
    except Exception as e:
        st.error(f"Error saving financial goal: {str(e)}")
        return False

def get_family_data(family_id, table_name):
    """Get family data from specific DynamoDB table"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.query(
            KeyConditionExpression='family_id = :fid',
            ExpressionAttributeValues={':fid': family_id}
        )
        return response['Items']
    except Exception as e:
        st.error(f"Error fetching data from {table_name}: {str(e)}")
        return []

def save_decision_history(family_id, decision_type, decision_description, amount_involved, decision_result, impact_assessment):
    """Save decision history to DynamoDB"""
    try:
        dynamodb = init_dynamodb()
        table = dynamodb.Table('DecisionHistory')
        
        decision_id = f"DEC{str(uuid.uuid4())[:6].upper()}"
        current_time = datetime.utcnow().isoformat() + "Z"
        
        item = {
            "family_id": family_id,
            "decision_timestamp_id": f"{current_time}#{decision_id}",
            "decision_type": decision_type,
            "decision_description": decision_description,
            "amount_involved": amount_involved,
            "decision_result": decision_result,
            "impact_assessment": impact_assessment,
            "decision_date_id": current_time
        }
        item = convert_floats(item)
        table.put_item(Item=item)
        return True
    except Exception as e:
        st.error(f"Error saving decision history: {str(e)}")
        return False

# Initialize session state
if 'show_signup' not in st.session_state:
    st.session_state.show_signup = False
if 'show_login' not in st.session_state:
    st.session_state.show_login = False
if 'show_success' not in st.session_state:
    st.session_state.show_success = False
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'family_id' not in st.session_state:
    st.session_state.family_id = None
if 'family_data' not in st.session_state:
    st.session_state.family_data = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'show_chat' not in st.session_state:
    st.session_state.show_chat = False

@st.dialog("Log In")
def log_in():
    """Login dialog for existing users"""
    with st.form("login_form"):
        st.markdown("### Welcome Back!")
        st.markdown("Log in to access your family finance dashboard")
        
        email = st.text_input("Email Address", placeholder="your@email.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_login = False
                st.rerun()
        
        if submitted:
            if email and password:
                with st.spinner("Authenticating..."):
                    success, result = authenticate_user(email, password)
                
                if success:
                    user_data = result
                    st.session_state.logged_in = True
                    st.session_state.family_id = user_data['family_id']
                    st.session_state.family_data = {
                        "family_name": user_data['family_name'],
                        "family_size": int(user_data['family_size']),
                        "location": user_data['location'],
                        "total_monthly_income": float(user_data['total_monthly_income']),
                        "risk_tolerance": user_data['risk_tolerance'],
                        "email": user_data['email']
                    }
                    st.session_state.show_login = False
                    
                    welcome_msg = f"""Welcome back, {user_data['family_name']}! I'm your family finance assistant.
                    
I have access to your family profile:
- Family ID: {user_data['family_id']}
- Monthly Income: ${float(user_data['total_monthly_income']):,.2f}
- Family Size: {user_data['family_size']}
- Risk Tolerance: {user_data['risk_tolerance']}

How can I help you with your financial decisions today?"""
                    
                    st.session_state.messages = [
                        {"role": "assistant", "content": welcome_msg}
                    ]
                    
                    st.success("Login successful!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {result}")
            else:
                st.error("Please enter both email and password")

@st.dialog("Sign up")
def sign_up():
    with st.form("signup_form"):
        st.markdown("### Create Your Family Account")
        st.markdown("Get started with personalized financial management")
        
        col1, col2 = st.columns(2)
        with col1:
            family_name = st.text_input("Family Name*", placeholder="The Smith Family")
            family_size = st.number_input("Family Size*", min_value=1, max_value=30, value=4)
            location = st.text_input("Country/Location*", placeholder="United States")
        
        with col2:
            total_monthly_income = st.number_input("Total Monthly Income ($)*", min_value=0.0, format="%.2f")
            risk_tolerance = st.selectbox("Risk Tolerance*", 
                                        options=["Conservative", "Moderate", "Aggressive"],
                                        help="Conservative: Low risk, stable returns\nModerate: Balanced risk and growth\nAggressive: High risk, high potential returns")
        
        st.markdown("---")
        st.markdown("### Account Credentials")
        
        email = st.text_input("Email Address*", placeholder="your@email.com")
        col1, col2 = st.columns(2)
        with col1:
            password = st.text_input("Password*", type="password", placeholder="Min. 6 characters")
        with col2:
            confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Re-enter password")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.show_signup = False
                st.rerun()
        
        if submitted:
            # Validation
            if not all([family_name, location, email, password]):
                st.error("Please fill in all required fields")
            elif total_monthly_income <= 0:
                st.error("Please enter a valid monthly income")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters long")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif '@' not in email:
                st.error("Please enter a valid email address")
            else:
                family_data = {
                    "family_name": family_name,
                    "family_size": family_size,
                    "location": location,
                    "total_monthly_income": total_monthly_income,
                    "risk_tolerance": risk_tolerance,
                    "email": email,
                    "password": password
                }
                
                with st.spinner("Creating your family account..."):
                    success, family_id = save_family_to_dynamodb(family_data)
                
                if success:
                    st.session_state.logged_in = True
                    st.session_state.family_id = family_id
                    st.session_state.family_data = family_data
                    st.session_state.show_signup = False
                    st.session_state.show_success = True
                    
                    welcome_msg = f"""Hello {family_name}! I'm your family finance assistant.
                    
I have access to your family profile:
- Family ID: {family_id}
- Monthly Income: ${total_monthly_income:,.2f}
- Family Size: {family_size}
- Risk Tolerance: {risk_tolerance}

How can I help you with your financial decisions today?"""
                    
                    st.session_state.messages = [
                        {"role": "assistant", "content": welcome_msg}
                    ]
                    
                    st.success("Account created successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to create account. Please try again.")

def open_signup():
    st.session_state.show_signup = True
    st.session_state.show_login = False

def open_login():
    st.session_state.show_login = True
    st.session_state.show_signup = False

def logout():
    """Logout and clear session state"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def display_chat_interface():
    """Display the chat interface with the Finance Agent"""
    st.markdown("### Financial Assistant Chat")
    
    if len(st.session_state.messages) > 1:
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🔄 Clear Chat", type="secondary", use_container_width=True):
                st.session_state.messages = [st.session_state.messages[0]]
                st.rerun()
    
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            if message["role"] in ["user", "assistant"]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask your financial assistant..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your financial data..."):
                try:
                    # from myfinance_agent import FinanceAgent
                    # from finance_updated import FinanceAgent
                    from master_agent import MasterAgent
                    
                    family_id = st.session_state.family_id
                    contextualized_query = f"Family ID: {family_id}\n\nQuery: {prompt}"
                    
                    # temp_agent = FinanceAgent()
                    # response = temp_agent.process_query(contextualized_query)
                    response = MasterAgent(contextualized_query)
                    
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    error_msg = f"Error processing your request: {str(e)}"
                    st.error(error_msg)
                    st.info("Try rephrasing your question or click 'Clear Chat' to start fresh.")

def display_data_management():
    """Display data management interface"""
    st.markdown("### Manage Your Financial Data")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Budget Allocations", 
        "💰 Expenses", 
        "🏦 Assets", 
        "🎯 Goals", 
        "📋 Decision History",
        "📈 View Data"
    ])
    
    family_id = st.session_state.family_id
    
    # Budget Allocations Tab
    with tab1:
        st.subheader("Add Budget Allocation")
        
        with st.form("budget_allocation_form"):
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Category", [
                    "Housing", "Food", "Transportation", "Healthcare", 
                    "Education", "Entertainment", "Utilities", "Insurance",
                    "Savings", "Debt Payment", "Other"
                ])
                allocated_amount = st.number_input("Allocated Amount ($)", min_value=0.0, format="%.2f")
            
            with col2:
                year_month = st.selectbox("Month", [
                    f"{datetime.now().year}-{str(month).zfill(2)}" 
                    for month in range(1, 13)
                ], index=datetime.now().month - 1)
                spent_amount = st.number_input("Already Spent ($)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("Add Budget Allocation", type="primary"):
                if allocated_amount > 0:
                    if save_budget_allocation(family_id, category, year_month, allocated_amount, spent_amount):
                        st.success(f"Budget allocation for {category} in {year_month} added successfully!")
                        st.rerun()
                else:
                    st.error("Please enter a valid allocated amount")
    
    # Expenses Tab
    with tab2:
        st.subheader("Add Expense Transaction")
        
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Amount ($)", min_value=0.0, format="%.2f")
                category = st.selectbox("Category", [
                    "Housing", "Food", "Transportation", "Healthcare", 
                    "Education", "Entertainment", "Utilities", "Insurance", "Other"
                ])
                subcategory = st.text_input("Subcategory", placeholder="e.g., Groceries, Gas, Rent")
            
            with col2:
                description = st.text_input("Description", placeholder="Brief description of expense")
                family_member = st.selectbox("Family Member", [
                    "Parent1", "Parent2", "Child1", "Child2", "Other"
                ])
                necessity_level = st.selectbox("Necessity Level", [
                    "Essential", "Important", "Optional"
                ])
            
            transaction_date = st.date_input("Transaction Date", value=date.today())
            
            if st.form_submit_button("Add Expense", type="primary"):
                if amount > 0 and category and description:
                    if save_expense_transaction(
                        family_id, amount, category, subcategory or "General", 
                        description, family_member, necessity_level, transaction_date
                    ):
                        st.success("Expense transaction added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in all required fields with valid values")
    
    # Assets Tab
    with tab3:
        st.subheader("Add Family Asset")
        
        with st.form("asset_form"):
            col1, col2 = st.columns(2)
            with col1:
                asset_name = st.text_input("Asset Name", placeholder="e.g., Emergency Savings, Investment Account")
                asset_type = st.selectbox("Asset Type", [
                    "Savings", "Investment", "Property", "Vehicle", "Other"
                ])
            
            with col2:
                current_value = st.number_input("Current Value ($)", min_value=0.0, format="%.2f")
                liquidity = st.selectbox("Liquidity Level", [
                    "High", "Medium", "Low"
                ], help="High: Can be accessed immediately\nMedium: Can be accessed within weeks\nLow: Takes months to access")
            
            if st.form_submit_button("Add Asset", type="primary"):
                if asset_name and current_value > 0:
                    if save_family_asset(family_id, asset_name, asset_type, current_value, liquidity):
                        st.success("Family asset added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in all required fields with valid values")
    
    # Goals Tab
    with tab4:
        st.subheader("Add Financial Goal")
        
        with st.form("goal_form"):
            col1, col2 = st.columns(2)
            with col1:
                goal_name = st.text_input("Goal Name", placeholder="e.g., Emergency Fund, Vacation")
                target_amount = st.number_input("Target Amount ($)", min_value=0.0, format="%.2f")
                current_amount = st.number_input("Current Amount ($)", min_value=0.0, format="%.2f")
            
            with col2:
                target_date = st.date_input("Target Date", value=date.today())
                priority = st.selectbox("Priority", [1, 2, 3, 4, 5], help="1 = Highest Priority, 5 = Lowest Priority")
                monthly_allocation = st.number_input("Monthly Allocation ($)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("Add Goal", type="primary"):
                if goal_name and target_amount > 0:
                    if save_financial_goal(
                        family_id, goal_name, target_amount, current_amount, 
                        target_date, priority, monthly_allocation
                    ):
                        st.success("Financial goal added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in all required fields with valid values")
    
    # Decision History Tab
    with tab5:
        st.subheader("Add Decision History")
        
        with st.form("decision_form"):
            col1, col2 = st.columns(2)
            with col1:
                decision_type = st.selectbox("Decision Type", [
                    "Purchase", "Investment", "Savings", "Budget Change", "Goal Adjustment", "Other"
                ])
                decision_description = st.text_area("Decision Description", 
                                                   placeholder="Describe the financial decision made...")
            
            with col2:
                amount_involved = st.number_input("Amount Involved ($)", min_value=0.0, format="%.2f")
                decision_result = st.selectbox("Decision Result", [
                    "Approved", "Denied", "Postponed", "Modified"
                ])
            
            impact_assessment = st.text_area("Impact Assessment", 
                                           placeholder="How will this decision impact your family's finances?")
            
            if st.form_submit_button("Add Decision Record", type="primary"):
                if decision_description and impact_assessment:
                    if save_decision_history(
                        family_id, decision_type, decision_description, 
                        amount_involved, decision_result, impact_assessment
                    ):
                        st.success("Decision history added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in the decision description and impact assessment")
    
    # View Data Tab
    with tab6:
        st.subheader("View Your Financial Data")
        
        data_type = st.selectbox("Select Data to View", [
            "Budget Allocations", "Expense Transactions", "Family Assets", 
            "Financial Goals", "Decision History"
        ])
        
        if st.button("Load Data", type="primary"):
            table_mapping = {
                "Budget Allocations": "BudgetAllocations",
                "Expense Transactions": "ExpenseTransactions", 
                "Family Assets": "FamilyAssets",
                "Financial Goals": "FinancialGoals",
                "Decision History": "DecisionHistory"
            }
            
            table_name = table_mapping[data_type]
            data = get_family_data(family_id, table_name)
            
            if data:
                # Convert Decimal objects to float for display
                display_data = []
                for item in data:
                    display_item = {}
                    for key, value in item.items():
                        if isinstance(value, Decimal):
                            display_item[key] = float(value)
                        else:
                            display_item[key] = value
                    display_data.append(display_item)
                
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True)
                
                # Add summary statistics
                if data_type == "Budget Allocations":
                    total_allocated = sum(float(item.get('allocated_amount', 0)) for item in data)
                    total_spent = sum(float(item.get('spent_amount', 0)) for item in data)
                    st.metric("Total Allocated", f"${total_allocated:,.2f}")
                    st.metric("Total Spent", f"${total_spent:,.2f}")
                    
                elif data_type == "Family Assets":
                    total_value = sum(float(item.get('current_value', 0)) for item in data)
                    st.metric("Total Asset Value", f"${total_value:,.2f}")
                    
                elif data_type == "Financial Goals":
                    total_target = sum(float(item.get('target_amount', 0)) for item in data)
                    total_current = sum(float(item.get('current_amount', 0)) for item in data)
                    st.metric("Total Goal Amount", f"${total_target:,.2f}")
                    st.metric("Total Saved", f"${total_current:,.2f}")
                    
            else:
                st.info(f"No {data_type.lower()} found for your family.")

# Main App
st.title("Family Finance Manager")

if st.session_state.logged_in and st.session_state.family_id:
    with st.sidebar:
        st.markdown(f"### {st.session_state.family_data['family_name']}")
        st.markdown(f"**Family ID:** `{st.session_state.family_id}`")
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            logout()
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard", "Financial Assistant", "Manage Data", "Reports", "Settings"
    ])
    
    with tab1:
        st.write(f"Welcome back, **{st.session_state.family_data['family_name']}**!")
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Monthly Income", f"${st.session_state.family_data['total_monthly_income']:,.0f}")
        with col2:
            st.metric("Family Size", st.session_state.family_data['family_size'])
        with col3:
            st.metric("Risk Level", st.session_state.family_data['risk_tolerance'])
        with col4:
            st.metric("Location", st.session_state.family_data['location'])
        
        st.markdown("---")
        
        # Budget breakdown (50/30/20 rule)
        st.subheader("Recommended Budget Allocation")
        income = st.session_state.family_data['total_monthly_income']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Needs (50%)**\n${income * 0.5:,.0f}")
            st.caption("Housing, utilities, groceries, insurance")
        with col2:
            st.warning(f"**Wants (30%)**\n${income * 0.3:,.0f}")
            st.caption("Entertainment, dining out, hobbies")
        with col3:
            st.success(f"**Savings (20%)**\n${income * 0.2:,.0f}")
            st.caption("Emergency fund, investments, debt payment")
        
        st.markdown("---")

        st.subheader("Quick Insights")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Emergency Fund Target**")
            emergency_fund = income * 6 
            st.write(f"Recommended: ${emergency_fund:,.0f}")
            st.caption("6 months of living expenses")
        with col2:
            st.write("**Annual Savings Potential**")
            annual_savings = income * 0.2 * 12
            st.write(f"Up to: ${annual_savings:,.0f}")
            st.caption("Based on 20% savings rate")
        
    with tab2:
        if len(st.session_state.messages) == 0:
            family_name = st.session_state.family_data['family_name']
            income = st.session_state.family_data['total_monthly_income']
            welcome_msg = f"""Hello {family_name}! I'm your personal finance assistant.
                    
I have access to your family profile and can help you with:
- Budget planning and allocation
- Spending decisions analysis
- Financial goal setting
- Finding alternative funding sources
- Impact analysis for major purchases

Your monthly income: ${income:,.2f}

What would you like to discuss today?"""
            st.session_state.messages = [{"role": "assistant", "content": welcome_msg}]
        
        display_chat_interface()
    
    with tab3:
        display_data_management()
    
    with tab4:
        st.subheader("Financial Reports & Analytics")
        
        # Summary metrics from database
        family_id = st.session_state.family_id
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Monthly Budget Overview")
            current_month = datetime.now().strftime("%Y-%m")
            budget_data = get_family_data(family_id, "BudgetAllocations")
            
            if budget_data:
                current_month_data = [item for item in budget_data if item.get('year_month') == current_month]
                if current_month_data:
                    total_allocated = sum(float(item.get('allocated_amount', 0)) for item in current_month_data)
                    total_spent = sum(float(item.get('spent_amount', 0)) for item in current_month_data)
                    remaining = total_allocated - total_spent
                    
                    st.metric("Total Allocated", f"${total_allocated:,.2f}")
                    st.metric("Total Spent", f"${total_spent:,.2f}")
                    st.metric("Remaining", f"${remaining:,.2f}")
                    
                    # Budget categories chart
                    if len(current_month_data) > 0:
                        categories = [item.get('category', 'Unknown') for item in current_month_data]
                        allocated = [float(item.get('allocated_amount', 0)) for item in current_month_data]
                        
                        chart_data = pd.DataFrame({
                            'Category': categories,
                            'Allocated': allocated
                        })
                        st.bar_chart(chart_data.set_index('Category'))
                else:
                    st.info(f"No budget allocations found for {current_month}")
            else:
                st.info("No budget data available. Add some budget allocations to see reports.")
        
        with col2:
            st.markdown("#### Asset Summary")
            asset_data = get_family_data(family_id, "FamilyAssets")
            
            if asset_data:
                total_assets = sum(float(item.get('current_value', 0)) for item in asset_data)
                st.metric("Total Assets", f"${total_assets:,.2f}")
                
                # Asset breakdown by type
                asset_types = {}
                for asset in asset_data:
                    asset_type = asset.get('asset_type', 'Unknown')
                    value = float(asset.get('current_value', 0))
                    asset_types[asset_type] = asset_types.get(asset_type, 0) + value
                
                if asset_types:
                    asset_df = pd.DataFrame(list(asset_types.items()), columns=['Type', 'Value'])
                    st.bar_chart(asset_df.set_index('Type'))
                
                # Liquidity breakdown
                st.markdown("##### Liquidity Levels")
                liquidity_levels = {}
                for asset in asset_data:
                    liquidity = asset.get('liquidity', 'Unknown')
                    value = float(asset.get('current_value', 0))
                    liquidity_levels[liquidity] = liquidity_levels.get(liquidity, 0) + value
                
                for level, value in liquidity_levels.items():
                    st.write(f"**{level}:** ${value:,.2f}")
            else:
                st.info("No asset data available. Add some assets to see reports.")
        
        st.markdown("---")
        
        # Goals Progress
        st.markdown("#### Financial Goals Progress")
        goals_data = get_family_data(family_id, "FinancialGoals")
        
        if goals_data:
            for goal in goals_data:
                goal_name = goal.get('goal_name', 'Unknown Goal')
                target = float(goal.get('target_amount', 0))
                current = float(goal.get('current_amount', 0))
                progress = (current / target * 100) if target > 0 else 0
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{goal_name}**")
                    st.progress(progress / 100)
                with col2:
                    st.metric("Progress", f"{progress:.1f}%")
                with col3:
                    st.metric("Remaining", f"${target - current:,.0f}")
        else:
            st.info("No financial goals set. Add some goals to track your progress.")
        
        st.markdown("---")
        
        # Recent Transactions
        st.markdown("#### Recent Transactions")
        transaction_data = get_family_data(family_id, "ExpenseTransactions")
        
        if transaction_data:
            # Sort by date (most recent first)
            sorted_transactions = sorted(transaction_data, 
                                       key=lambda x: x.get('transaction_date', ''), 
                                       reverse=True)[:10]  # Show last 10
            
            for transaction in sorted_transactions:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
                with col1:
                    st.write(f"**{transaction.get('description', 'N/A')}**")
                with col2:
                    st.write(f"${float(transaction.get('amount', 0)):,.2f}")
                with col3:
                    st.write(transaction.get('category', 'N/A'))
                with col4:
                    st.write(transaction.get('transaction_date', 'N/A'))
        else:
            st.info("No transaction data available. Add some expense transactions to see recent activity.")
    
    with tab5:
        st.subheader("Account Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Family Information**")
            st.write(f"Family ID: `{st.session_state.family_id}`")
            st.write(f"Family Name: {st.session_state.family_data['family_name']}")
            st.write(f"Email: {st.session_state.family_data['email']}")
            st.write(f"Member Since: {datetime.now().strftime('%B %Y')}")
        
        with col2:
            st.write("**Financial Profile**")
            st.write(f"Monthly Income: ${st.session_state.family_data['total_monthly_income']:,.2f}")
            st.write(f"Family Size: {st.session_state.family_data['family_size']}")
            st.write(f"Location: {st.session_state.family_data['location']}")
            st.write(f"Risk Tolerance: {st.session_state.family_data['risk_tolerance']}")
        
        st.markdown("---")
        
        st.subheader("Update Profile")
        with st.expander("Edit Financial Information"):
            with st.form("update_profile"):
                new_income = st.number_input("Monthly Income ($)", 
                                            value=st.session_state.family_data['total_monthly_income'],
                                            min_value=0.0, format="%.2f")
                new_family_size = st.number_input("Family Size", 
                                                 value=st.session_state.family_data['family_size'],
                                                 min_value=1, max_value=30)
                new_risk = st.selectbox("Risk Tolerance", 
                                       options=["Conservative", "Moderate", "Aggressive"],
                                       index=["Conservative", "Moderate", "Aggressive"].index(
                                           st.session_state.family_data['risk_tolerance']))
                
                if st.form_submit_button("Update Profile"):
                    st.session_state.family_data['total_monthly_income'] = new_income
                    st.session_state.family_data['family_size'] = new_family_size
                    st.session_state.family_data['risk_tolerance'] = new_risk
                    
                    try:
                        dynamodb = init_dynamodb()
                        table = dynamodb.Table('FamilyProfiles')
                        table.update_item(
                            Key={'family_id': st.session_state.family_id},
                            UpdateExpression='SET total_monthly_income = :income, family_size = :size, risk_tolerance = :risk, updated_at = :updated',
                            ExpressionAttributeValues={
                                ':income': Decimal(str(new_income)),
                                ':size': new_family_size,
                                ':risk': new_risk,
                                ':updated': datetime.utcnow().isoformat() + "Z"
                            }
                        )
                        st.success("Profile updated successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating profile: {str(e)}")
        
        st.markdown("---")
        
        # Data Export
        st.subheader("Data Export")
        with st.expander("Export Your Data"):
            export_type = st.selectbox("Select data to export", [
                "All Data", "Budget Allocations", "Expense Transactions", 
                "Family Assets", "Financial Goals", "Decision History"
            ])
            
            if st.button("Export Data", type="secondary"):
                family_id = st.session_state.family_id
                
                if export_type == "All Data":
                    all_data = {}
                    for table in ["BudgetAllocations", "ExpenseTransactions", "FamilyAssets", "FinancialGoals", "DecisionHistory"]:
                        data = get_family_data(family_id, table)
                        # Convert Decimals for JSON serialization
                        converted_data = []
                        for item in data:
                            converted_item = {}
                            for key, value in item.items():
                                if isinstance(value, Decimal):
                                    converted_item[key] = float(value)
                                else:
                                    converted_item[key] = value
                            converted_data.append(converted_item)
                        all_data[table] = converted_data
                    
                    st.download_button(
                        label="Download All Data (JSON)",
                        data=pd.DataFrame(all_data).to_json(),
                        file_name=f"{family_id}_all_data_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )
                else:
                    table_mapping = {
                        "Budget Allocations": "BudgetAllocations",
                        "Expense Transactions": "ExpenseTransactions", 
                        "Family Assets": "FamilyAssets",
                        "Financial Goals": "FinancialGoals",
                        "Decision History": "DecisionHistory"
                    }
                    
                    table_name = table_mapping[export_type]
                    data = get_family_data(family_id, table_name)
                    
                    if data:
                        # Convert Decimals to float for CSV
                        display_data = []
                        for item in data:
                            display_item = {}
                            for key, value in item.items():
                                if isinstance(value, Decimal):
                                    display_item[key] = float(value)
                                else:
                                    display_item[key] = value
                            display_data.append(display_item)
                        
                        df = pd.DataFrame(display_data)
                        csv = df.to_csv(index=False)
                        
                        st.download_button(
                            label=f"Download {export_type} (CSV)",
                            data=csv,
                            file_name=f"{family_id}_{export_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.error(f"No {export_type.lower()} data found to export.")
        
        st.markdown("---")
        
        # Danger zone
        st.subheader("Danger Zone")
        with st.expander("Delete Account"):
            st.warning("**Warning:** This action cannot be undone. All your data will be permanently deleted.")
            
            delete_confirmation = st.text_input("Type 'DELETE' to confirm account deletion:")
            
            if delete_confirmation == "DELETE":
                if st.button("Delete My Account", type="secondary"):
                    try:
                        dynamodb = init_dynamodb()
                        
                        # Delete from all tables
                        tables_to_clean = [
                            "FamilyProfiles", "BudgetAllocations", "ExpenseTransactions", 
                            "FamilyAssets", "FinancialGoals", "DecisionHistory"
                        ]
                        
                        for table_name in tables_to_clean:
                            table = dynamodb.Table(table_name)
                            
                            # Get all items for this family
                            try:
                                if table_name == "FamilyProfiles":
                                    table.delete_item(Key={'family_id': st.session_state.family_id})
                                else:
                                    response = table.query(
                                        KeyConditionExpression='family_id = :fid',
                                        ExpressionAttributeValues={':fid': st.session_state.family_id}
                                    )
                                    
                                    # Delete each item
                                    for item in response['Items']:
                                        if table_name == "BudgetAllocations":
                                            table.delete_item(Key={
                                                'family_id': item['family_id'],
                                                'category_month': item['category_month']
                                            })
                                        elif table_name == "ExpenseTransactions":
                                            table.delete_item(Key={
                                                'family_id': item['family_id'],
                                                'transaction_date_id': item['transaction_date_id']
                                            })
                                        elif table_name == "FamilyAssets":
                                            table.delete_item(Key={
                                                'family_id': item['family_id'],
                                                'asset_type_id': item['asset_type_id']
                                            })
                                        elif table_name == "FinancialGoals":
                                            table.delete_item(Key={
                                                'family_id': item['family_id'],
                                                'goal_id': item['goal_id']
                                            })
                                        elif table_name == "DecisionHistory":
                                            table.delete_item(Key={
                                                'family_id': item['family_id'],
                                                'decision_timestamp_id': item['decision_timestamp_id']
                                            })
                            except Exception as e:
                                st.error(f"Error deleting from {table_name}: {str(e)}")
                        
                        st.success("Account deleted successfully. Redirecting...")
                        time.sleep(2)
                        logout()
                        
                    except Exception as e:
                        st.error(f"Error deleting account: {str(e)}")

else:
    st.write("Welcome to your personal family finance management system!")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Get Started")
        
        st.button("Login to Existing Account", 
                    on_click=open_login,
                    type="primary",
                    use_container_width=True)
        
        st.button("Create New Family Account", 
                    on_click=open_signup,
                    type="secondary",
                    use_container_width=True)

# Handle dialog states
if st.session_state.show_signup:
    sign_up()

if st.session_state.show_login:
    log_in()

if st.session_state.show_success and st.session_state.family_id:
    st.session_state.show_success = False