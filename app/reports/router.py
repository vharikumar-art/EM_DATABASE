import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUser, get_current_user
from app.database.mongodb import get_collection
from app.employees.service import get_employee_by_user_id

router = APIRouter(prefix="/reports", tags=["Reports"])

EXPORT_FIELDS = [
    "fullName", "email", "company", "website", "country", "state", "city",
    "domain", "industry", "designation", "phone", "linkedin", "uploadBatch",
    "isDuplicate", "createdAt",
]


@router.get("/emails/export")
async def export_emails_csv(
    employeeId: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Streams the caller's (or, for admins, a chosen employee's) lead list as CSV."""
    if current_user.role == "admin":
        target_employee_id = employeeId
    else:
        employee = await get_employee_by_user_id(current_user.user_id)
        target_employee_id = employee["id"]

    query = {"employeeId": target_employee_id} if target_employee_id else {}
    emails = get_collection("emails")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()

    async for doc in emails.find(query).sort("createdAt", -1):
        writer.writerow(doc)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=emails_export.csv"},
    )
