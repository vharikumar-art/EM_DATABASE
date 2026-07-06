import uuid
from datetime import datetime, timezone

from app.core.exceptions import BadRequestException
from app.database.mongodb import get_collection
from app.emails.model import build_email_document
from app.logs.model import LogAction, build_log_document
from app.profiles.service import get_profile
from app.schemas.common import PaginationParams
from app.utils.csv_utils import parse_file_bytes, validate_and_clean_rows
from app.utils.pagination import build_paginated_response
from app.utils.response import serialize_list

COLLECTION = "emails"


async def upload_file(employee_id: str, file_bytes: bytes, filename: str, insert_duplicates: bool = False) -> dict:
    emails = get_collection(COLLECTION)

    try:
        df = parse_file_bytes(file_bytes, filename)
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc

    valid_rows, failed_count = validate_and_clean_rows(df)
    if not valid_rows:
        raise BadRequestException("No valid email rows found in the uploaded file")

    upload_batch = f"batch_{uuid.uuid4().hex[:12]}"

    # Extract all email addresses from the uploaded batch
    batch_emails = [row["email"] for row in valid_rows]

    # Query the database only for the emails present in this batch
    existing_cursor = emails.find({"employeeId": employee_id, "email": {"$in": batch_emails}}, {"email": 1})
    existing_emails = {doc["email"] async for doc in existing_cursor}

    docs_to_insert = []
    seen_in_batch: set[str] = set()
    unique_count = 0
    duplicate_count = 0

    for row in valid_rows:
        email_addr = row["email"]
        is_dup = email_addr in existing_emails or email_addr in seen_in_batch
        if is_dup:
            duplicate_count += 1
            if not insert_duplicates:
                continue
        else:
            unique_count += 1
            seen_in_batch.add(email_addr)

        docs_to_insert.append(build_email_document(employee_id, upload_batch, is_dup, row))

    if docs_to_insert:
        await emails.insert_many(docs_to_insert)

    logs = get_collection("logs")
    await logs.insert_one(
        build_log_document(
            employee_id=employee_id,
            profile_id=None,
            action=LogAction.UPLOAD,
            uploaded_count=len(valid_rows) + failed_count,
            unique_count=unique_count,
            duplicate_count=duplicate_count,
            sent_count=0,
            run_date=datetime.now(timezone.utc),
        )
    )

    return {
        "totalUploaded": len(valid_rows) + failed_count,
        "unique": unique_count,
        "duplicate": duplicate_count,
        "failed": failed_count,
        "uploadBatch": upload_batch,
    }


async def list_emails(
    employee_id: str | None,
    params: PaginationParams,
    country: str | None = None,
    domain: str | None = None,
    include_duplicates: bool = True,
):
    emails = get_collection(COLLECTION)
    query: dict = {}
    if employee_id:
        query["employeeId"] = employee_id
    if country:
        query["country"] = country
    if domain:
        query["domain"] = domain
    if not include_duplicates:
        query["isDuplicate"] = False

    total = await emails.count_documents(query)
    cursor = (
        emails.find(query)
        .sort("createdAt", -1)
        .skip(params.skip)
        .limit(params.pageSize)
    )
    docs = serialize_list([d async for d in cursor])
    return build_paginated_response(docs, total, params)


async def get_emails_for_profile(profile_id: str, employee_id: str, is_admin: bool):
    """Dynamically query the emails collection using a profile's stored filter options."""
    profile = await get_profile(profile_id, employee_id, is_admin)
    options = profile["options"]

    query: dict = {"employeeId": profile["employeeId"], "isDuplicate": False}
    if options.get("country"):
        query["country"] = {"$in": options["country"]}
    if options.get("domain"):
        query["domain"] = {"$in": options["domain"]}
    if options.get("type"):
        # "type" maps to designation/industry style filters depending on how the
        # employee tags rows; matched against both fields for flexibility.
        query["$or"] = [
            {"industry": {"$in": options["type"]}},
            {"designation": {"$in": options["type"]}},
        ]

    daily_limit = options.get("dailyLimit", 100)

    emails = get_collection(COLLECTION)
    cursor = emails.find(query).limit(daily_limit)
    docs = serialize_list([d async for d in cursor])
    return docs
