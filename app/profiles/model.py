from datetime import datetime, timezone
from typing import Any

MAX_PROFILES_PER_EMPLOYEE = 5


def build_profile_document(
    employee_id: str, profile_name: str, gmail_account: str, options: dict[str, Any]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "employeeId": employee_id,
        "profileName": profile_name,
        "gmailAccount": gmail_account,
        "isActive": True,
        "options": options,
        "createdAt": now,
        "updatedAt": now,
    }
