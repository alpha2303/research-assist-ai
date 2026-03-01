"""One-time migration: convert random UUID message IDs to timestamp-prefixed IDs.

Run inside the backend container:
    python scripts/migrate_message_ids.py
"""

import boto3
import os
from datetime import datetime

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localstack:4566")
ddb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
table = ddb.Table(
    os.environ.get("DYNAMODB_CHAT_MESSAGES_TABLE", "research-assist-chat-messages-dev")
)

resp = table.scan()
items = resp.get("Items", [])
print(f"Found {len(items)} messages to migrate")

for item in items:
    old_id = item["message_id"]
    ts = item.get("timestamp", "")

    # Already migrated?
    if "#" in old_id:
        print(f"  Skip (already migrated): {old_id[:30]}")
        continue

    # Parse timestamp and create new ID
    dt = datetime.fromisoformat(ts)
    new_id = f"{dt.strftime('%Y%m%dT%H%M%S%f')}#{old_id}"

    # Delete old item, insert with new key
    table.delete_item(Key={"chat_id": item["chat_id"], "message_id": old_id})
    item["message_id"] = new_id
    table.put_item(Item=item)
    print(f"  Migrated: {old_id[:8]} -> {new_id[:30]}...")

print("Migration complete")
