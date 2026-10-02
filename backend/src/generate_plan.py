"""POST /plans {employeeId} - generate a personalised 3-week onboarding plan.

1. Fetch the employee profile.
2. Rank the training catalogue by cosine similarity to the employee's role/team (embeddings).
3. Ask the LLM to build a concise 3-week plan using ONLY the selected modules (limits hallucination).
4. Store the plan in DynamoDB with status PENDING_REVIEW for HR approval.
"""
import uuid

import llm
from common import audit, find_employee, load_json, now_iso, parse_body, put_plan, response

TOP_K = 8


def select_modules(employee, catalogue):
    profile = f"{employee['role']} in {employee['team']}. Skills: {', '.join(employee.get('skills', []))}"
    texts = [profile] + [f"{m['title']}. {m['description']} Tags: {', '.join(m['tags'])}" for m in catalogue]
    vectors = llm.embed(texts)
    scored = [(llm.cosine(vectors[0], v), m) for v, m in zip(vectors[1:], catalogue)]
    mandatory = [m for m in catalogue if m.get("mandatory")]
    ranked = [m for _, m in sorted(scored, key=lambda s: s[0], reverse=True) if not m.get("mandatory")]
    return mandatory + ranked[: max(TOP_K - len(mandatory), 0)]


def llm_plan(employee, modules):
    catalogue = "\n".join(f"- {m['id']}: {m['title']} ({m['hours']}h) - {m['description']}" for m in modules)
    prompt = f"""You are an HR onboarding assistant. Create a concise 3-week onboarding plan for this new joiner.
Use ONLY the training modules listed below (refer to them by id). Do not invent modules.

New joiner: {employee['name']}, {employee['role']}, {employee['team']} team, manager {employee['manager']}, starts {employee['startDate']}.

Training modules:
{catalogue}

Return JSON exactly in this shape:
{{"summary": "2 sentences", "weeks": [{{"week": 1, "theme": "...", "items": [{{"moduleId": "...", "day": "Mon-Tue", "goal": "one short line"}}]}}]}}
Three weeks, 2-4 items per week. Week 1 must include all mandatory modules."""
    return llm.generate_json(prompt)


def template_plan(employee, modules):
    """Deterministic fallback when no LLM key is configured or the LLM call fails."""
    themes = ["Settle in & essentials", "Team tools & systems", "First contributions"]
    days = ["Mon-Tue", "Wed-Thu", "Fri"]
    weeks = [{"week": i + 1, "theme": t, "items": []} for i, t in enumerate(themes)]
    for i, m in enumerate(modules):
        week = 0 if m.get("mandatory") else min(1 + (i // 3) % 2, 2)
        weeks[week]["items"].append({"moduleId": m["id"], "day": days[len(weeks[week]["items"]) % 3], "goal": m["description"]})
    return {
        "summary": f"A 3-week plan to help {employee['name']} ramp up as {employee['role']} in {employee['team']}.",
        "weeks": weeks,
    }


def handler(event, _context):
    employee = find_employee(parse_body(event).get("employeeId"))
    if not employee:
        return response(404, {"message": "Employee not found"})

    catalogue = load_json("training_catalogue.json")
    modules = select_modules(employee, catalogue)
    source = "llm"
    try:
        if not llm.available():
            raise RuntimeError("no LLM key configured")
        plan = llm_plan(employee, modules)
    except Exception as exc:  # free-tier limits, timeouts, malformed output
        print(f"LLM unavailable, using template planner: {exc}")
        plan, source = template_plan(employee, modules), "template"

    by_id = {m["id"]: m for m in modules}
    for week in plan.get("weeks", []):
        week["items"] = [dict(item, **{k: by_id[item["moduleId"]][k] for k in ("title", "hours", "link")})
                         for item in week.get("items", []) if item.get("moduleId") in by_id]

    record = {
        "planId": str(uuid.uuid4()),
        "employeeId": employee["employeeId"],
        "employee": employee,
        "plan": plan,
        "generatedBy": source,
        "status": "PENDING_REVIEW",
        "version": 1,
        "createdAt": now_iso(),
    }
    audit(record, "GENERATED", "athena", f"{len(modules)} modules selected by cosine similarity ({source})")
    put_plan(record)
    return response(201, record)
