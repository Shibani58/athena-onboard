"""POST /plans/{planId}/send - email an APPROVED plan to the new joiner via SES.

If SENDER_EMAIL is not configured (public demo), nothing is sent: the rendered email
is returned as a preview and the action is still logged in the audit trail.
"""
import html
import os

from common import audit, get_plan, put_plan, response


def render_email(record):
    emp, plan = record["employee"], record["plan"]
    rows = []
    for week in plan.get("weeks", []):
        rows.append(f"<h3>Week {week['week']}: {html.escape(week.get('theme', ''))}</h3><ul>")
        for item in week.get("items", []):
            rows.append(f"<li><b>{html.escape(item.get('day', ''))}</b> - {html.escape(item.get('title', ''))} "
                        f"({item.get('hours', '?')}h): {html.escape(item.get('goal', ''))}</li>")
        rows.append("</ul>")
    subject = f"Welcome aboard, {emp['name'].split()[0]}! Your 3-week onboarding plan"
    body = (f"<p>Hi {html.escape(emp['name'])},</p><p>{html.escape(plan.get('summary', ''))}</p>"
            + "".join(rows)
            + f"<p>Your manager {html.escape(emp['manager'])} will check in with you at the end of each week.</p>"
            + f"<p style='color:#888'>Plan ID {record['planId']} · version {record.get('version', 1)}</p>")
    return subject, body


def handler(event, _context):
    plan_id = (event.get("pathParameters") or {}).get("planId")
    record = get_plan(plan_id)
    if not record:
        return response(404, {"message": "Plan not found"})
    if record["status"] not in ("APPROVED", "SENT"):
        return response(409, {"message": "Plan must be approved by HR before sending"})

    subject, body = render_email(record)
    sender = os.environ.get("SENDER_EMAIL", "").strip()
    to = record["employee"]["email"]
    if sender:
        import boto3
        boto3.client("ses").send_email(
            Source=sender,
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject}, "Body": {"Html": {"Data": body}}},
        )
        mode = "sent"
    else:
        mode = "preview"

    record["status"] = "SENT"
    audit(record, "EMAIL_SENT" if mode == "sent" else "EMAIL_PREVIEWED", "athena", to)
    put_plan(record)
    return response(200, {"mode": mode, "to": to, "subject": subject, "html": body, "plan": record})
