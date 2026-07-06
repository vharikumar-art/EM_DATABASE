from app.database.mongodb import get_collection
from app.logs.model import LogAction, build_log_document
from app.logs.schema import CampaignLogUpdate
from app.schemas.common import PaginationParams
from app.utils.pagination import build_paginated_response
from app.utils.response import serialize_list

COLLECTION = "logs"


async def list_logs(employee_id: str | None, params: PaginationParams):
    logs = get_collection(COLLECTION)
    query = {"employeeId": employee_id} if employee_id else {}
    total = await logs.count_documents(query)
    cursor = logs.find(query).sort("createdAt", -1).skip(params.skip).limit(params.pageSize)
    docs = serialize_list([d async for d in cursor])
    return build_paginated_response(docs, total, params)


async def record_campaign_start(employee_id: str, profile_id: str) -> dict:
    logs = get_collection(COLLECTION)
    doc = build_log_document(
        employee_id=employee_id, profile_id=profile_id, action=LogAction.CAMPAIGN_STARTED
    )
    result = await logs.insert_one(doc)
    created = await logs.find_one({"_id": result.inserted_id})
    from app.utils.response import serialize_doc

    return serialize_doc(created)


async def record_campaign_completion(payload: CampaignLogUpdate) -> dict:
    """Called by n8n once a campaign finishes sending, to persist final sent counts."""
    logs = get_collection(COLLECTION)

    # Look up the owning employee from the profile so the log is correctly attributed.
    profiles = get_collection("profiles")
    from app.utils.response import to_object_id

    profile = await profiles.find_one({"_id": to_object_id(payload.profileId)})
    if not profile:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Profile not found for this campaign log")

    doc = build_log_document(
        employee_id=str(profile["employeeId"]),
        profile_id=payload.profileId,
        action=LogAction.CAMPAIGN_COMPLETED,
        sent_count=payload.sentCount,
        run_date=payload.runDate,
    )
    result = await logs.insert_one(doc)
    created = await logs.find_one({"_id": result.inserted_id})
    from app.utils.response import serialize_doc

    return serialize_doc(created)
