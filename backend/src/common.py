"""Shared helpers: HTTP responses, synthetic data, DynamoDB plan store."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
_table = None


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": os.environ.get("ALLOWED_ORIGIN", "*"),
        },
        "body": json.dumps(body, default=str),
    }


def parse_body(event):
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def find_employee(employee_id):
    """Mock HR system lookup (synthetic data bundled with the function)."""
    employee_id = (employee_id or "").strip().upper()
    return next((e for e in load_json("employees.json") if e["employeeId"] == employee_id), None)


def plans_table():
    global _table
    if _table is None:
        import boto3
        _table = boto3.resource("dynamodb").Table(os.environ["PLANS_TABLE"])
    return _table


def get_plan(plan_id):
    return plans_table().get_item(Key={"planId": plan_id}).get("Item")


def put_plan(plan):
    plans_table().put_item(Item=plan)
    return plan


def audit(plan, action, actor, note=""):
    plan.setdefault("audit", []).append({"at": now_iso(), "action": action, "by": actor, "note": note})
