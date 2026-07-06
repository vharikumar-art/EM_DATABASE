from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


def build_employee_document(user_id: str, employee_code: str | None = None, department: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "userId": user_id,
        "employeeCode": employee_code,
        "department": department,
        "status": EmployeeStatus.ACTIVE.value,
        "createdAt": now,
        "updatedAt": now,
    }
