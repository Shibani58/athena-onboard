"""GET /employees/{employeeId} - fetch a new joiner from the (mock) HR system."""
from common import find_employee, response


def handler(event, _context):
    employee_id = (event.get("pathParameters") or {}).get("employeeId")
    employee = find_employee(employee_id)
    if not employee:
        return response(404, {"message": f"No employee found with ID {employee_id}"})
    return response(200, employee)
