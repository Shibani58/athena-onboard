"""GET /plans/{planId} - fetch a plan.
PUT /plans/{planId} {decision: APPROVED|REJECTED, reviewer, note, plan?} - HR review (human in the loop).
Edits bump the version; every action is kept in the audit trail.
"""
from common import audit, get_plan, parse_body, put_plan, response

DECISIONS = {"APPROVED", "REJECTED"}


def handler(event, _context):
    plan_id = (event.get("pathParameters") or {}).get("planId")
    record = get_plan(plan_id)
    if not record:
        return response(404, {"message": "Plan not found"})

    if event.get("requestContext", {}).get("http", {}).get("method") == "GET":
        return response(200, record)

    body = parse_body(event)
    decision = (body.get("decision") or "").upper()
    if decision not in DECISIONS:
        return response(400, {"message": "decision must be APPROVED or REJECTED"})
    if record["status"] == "SENT":
        return response(409, {"message": "Plan already sent"})

    reviewer = body.get("reviewer") or "HR reviewer"
    if body.get("plan"):
        record["plan"] = body["plan"]
        record["version"] = int(record.get("version", 1)) + 1
        audit(record, "EDITED", reviewer, f"version {record['version']}")
    record["status"] = decision
    audit(record, decision, reviewer, body.get("note", ""))
    put_plan(record)
    return response(200, record)
