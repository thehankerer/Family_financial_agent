import boto3
import json
import sys
import os
import datetime

def create_dynamodb_table(table_name, key_name, region='us-east-1'):
    dynamodb = boto3.resource('dynamodb', region_name=region)
    existing_tables = [table.name for table in dynamodb.tables.all()]
    if table_name in existing_tables:
        print(f"Table '{table_name}' already exists.")
        return dynamodb.Table(table_name)
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {'AttributeName': key_name, 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': key_name, 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table.wait_until_exists()
    print(f"Table '{table_name}' created.")
    return table

def upload_json_to_table(table, json_file, key_name):
    if not os.path.isfile(json_file):
        print(f"File '{json_file}' not found.")
        return
    with open(json_file, 'r') as f:
        data = json.load(f)
    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        print("JSON file must contain an object or a list of objects.")
        return
    for item in items:
        if key_name not in item:
            print(f"Item missing key '{key_name}': {item}")
            continue
        table.put_item(Item=item)
    print(f"Uploaded {len(items)} items to table '{table.name}'.")

# ...existing code...

def get_item_by_key(table, key_name, key_value):
    response = table.get_item(Key={key_name: key_value})
    item = response.get('Item')
    if item:
        print(f"Item found: {item}")
        return item
    else:
        print(f"No item found with {key_name} = {key_value}")
        return None




def get_item_by_nearest_key(table, key_name, key_value):
    """
    Iterates through all items in the table and finds the item whose key is closest
    (by string comparison) to the input key_value.
    """
    closest_item = None
    closest_diff = None

    scan_kwargs = {}
    done = False
    start_key = None

    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        for item in items:
            item_key = item.get(key_name)
            if item_key is not None:
                # Use string comparison: absolute difference in Unicode code points
                diff = abs(ord(item_key[0]) - ord(key_value[0]))
                if closest_diff is None or diff < closest_diff:
                    closest_diff = diff
                    closest_item = item
        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

    if closest_item:
        print(f"Closest item found: {closest_item}")
        return closest_item
    else:
        print(f"No items found in table for key '{key_name}'.")
        return None


# ...existing code...

if __name__ == "__main__":
    print(len(sys.argv))
    if len(sys.argv) != 4:
        print("Usage: python upload_to_dynamodb.py <table_name> <key_name> <json_file>")
        sys.exit(1)
    #table_name = sys.argv[1]
    #key_value = sys.argv[2]
    table_name = "test_table"
    key_name = "dateTime" 
# Get current dateTime as key_name
    #key_value = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = "01/31/25"
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    key_value = f"{date_str} {current_time}"
    print(f"Retrieving item with key value: {key_value}")
    json_file = sys.argv[3]
    table = create_dynamodb_table(table_name, key_name)
    upload_json_to_table(table, json_file, key_name)
    
    item = get_item_by_nearest_key(table, key_name, key_value)
    print(item)
        # Get the bpm value from the item
        # Get the bpm value from the item
    bpm_value = item.get('bpm')
    if bpm_value is not None:
        print(f"bpm value: {bpm_value}")
    else:
        print("bpm value not found in item.")