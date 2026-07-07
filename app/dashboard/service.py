from datetime import datetime, timedelta, timezone

from app.dashboard.schema import DashboardQuery
from app.dashboard.utils import resolve_date_range
from app.database.mongodb import get_collection
from app.utils.response import serialize_list


async def _count_uploads_since(employee_id: str, since: datetime) -> int:
    emails = get_collection("emails")
    return await emails.count_documents({"employeeId": employee_id, "createdAt": {"$gte": since}})


async def get_employee_dashboard(employee_id: str, query: DashboardQuery) -> dict:
    emails = get_collection("emails")
    logs = get_collection("logs")
    profiles = get_collection("profiles")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7_start = today_start - timedelta(days=6)

    start_dt, end_dt = resolve_date_range(query)
    range_match = {"employeeId": employee_id, "createdAt": {"$gte": start_dt, "$lte": end_dt}}

    today_upload_count = await _count_uploads_since(employee_id, today_start)
    last_7_days_upload_count = await _count_uploads_since(employee_id, last_7_start)

    unique_count = await emails.count_documents({**range_match, "isDuplicate": False})

    sent_pipeline = [
        {
            "$match": {
                "employeeId": employee_id,
                "action": "CAMPAIGN_COMPLETED",
                "runDate": {"$gte": start_dt, "$lte": end_dt},
            }
        },
        {"$group": {"_id": None, "totalSent": {"$sum": "$sentCount"}}},
    ]
    sent_result = await logs.aggregate(sent_pipeline).to_list(length=1)
    sent_email_count = sent_result[0]["totalSent"] if sent_result else 0

    # Profile-level stats: uploads attributed to a profile aren't tracked directly on
    # the email doc, so we report sent counts per profile plus each profile's overall
    # upload-eligible lead count (matching its filters) as a proxy for "uploaded".
    profile_stats = []
    async for profile in profiles.find({"employeeId": employee_id}):
        profile_id_str = str(profile["_id"])
        sent_for_profile = await logs.aggregate(
            [
                {
                    "$match": {
                        "profileId": profile_id_str,
                        "action": "CAMPAIGN_COMPLETED",
                        "runDate": {"$gte": start_dt, "$lte": end_dt},
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$sentCount"}}},
            ]
        ).to_list(length=1)
        uploaded_for_profile = await emails.count_documents(
            {
                "employeeId": employee_id,
                "isDuplicate": False,
                "country": {"$in": profile["options"].get("country", [])} if profile["options"].get("country") else {"$exists": True},
            }
        )
        profile_stats.append(
            {
                "profileId": profile_id_str,
                "profileName": profile["profileName"],
                "uploadedCount": uploaded_for_profile,
                "sentCount": sent_for_profile[0]["total"] if sent_for_profile else 0,
            }
        )

    recent_upload_cursor = (
        logs.find({"employeeId": employee_id, "action": "UPLOAD"}).sort("createdAt", -1).limit(10)
    )
    recent_upload_history = serialize_list([d async for d in recent_upload_cursor])

    total_upload_count = await emails.count_documents(range_match)

    return {
        "todayUploadCount": today_upload_count,
        "last7DaysUploadCount": last_7_days_upload_count,
        "totalUploadCount": total_upload_count,
        "uniqueEmailCount": unique_count,
        "sentEmailCount": sent_email_count,
        "profileStatistics": profile_stats,
        "recentUploadHistory": recent_upload_history,
    }


async def get_admin_dashboard(query: DashboardQuery) -> dict:
    employees = get_collection("employees")
    emails = get_collection("emails")
    logs = get_collection("logs")
    profiles = get_collection("profiles")

    start_dt, end_dt = resolve_date_range(query)
    range_match = {"createdAt": {"$gte": start_dt, "$lte": end_dt}}

    total_employees = await employees.count_documents({})
    total_uploads = await emails.count_documents(range_match)
    total_unique_emails = await emails.count_documents({**range_match, "isDuplicate": False})

    # Employee ranking: uploads + sent counts within range, grouped by employeeId.
    ranking_pipeline = [
        {"$match": range_match},
        {"$group": {"_id": "$employeeId", "uploadedCount": {"$sum": 1}}},
        {"$sort": {"uploadedCount": -1}},
        {"$limit": 20},
    ]
    ranking_rows = await emails.aggregate(ranking_pipeline).to_list(length=20)

    sent_pipeline = [
        {"$match": {"action": "CAMPAIGN_COMPLETED", "runDate": {"$gte": start_dt, "$lte": end_dt}}},
        {"$group": {"_id": "$employeeId", "sentCount": {"$sum": "$sentCount"}}},
    ]
    sent_rows = {row["_id"]: row["sentCount"] async for row in logs.aggregate(sent_pipeline)}

    employee_ranking = []
    employee_statistics = []
    for row in ranking_rows:
        emp_id = row["_id"]
        employee_doc = await employees.find_one({"_id": _safe_object_id(emp_id)})
        emp_name = None
        if employee_doc:
            user = await get_collection("users").find_one({"_id": _safe_object_id(employee_doc["userId"])})
            emp_name = user["name"] if user else employee_doc.get("employeeCode")

        entry = {
            "employeeId": emp_id,
            "employeeName": emp_name or "Unknown",
            "uploadedCount": row["uploadedCount"],
            "sentCount": sent_rows.get(emp_id, 0),
        }
        employee_ranking.append(entry)
        employee_statistics.append(entry)

    recent_activities_cursor = logs.find({}).sort("createdAt", -1).limit(20)
    recent_activities = serialize_list([d async for d in recent_activities_cursor])

    profile_usage_pipeline = [
        {"$group": {"_id": "$employeeId", "profileCount": {"$sum": 1}}},
    ]
    profile_usage = [
        {"employeeId": row["_id"], "profileCount": row["profileCount"]}
        async for row in profiles.aggregate(profile_usage_pipeline)
    ]

    # Total sent across the date range
    total_sent_pipeline = [
        {"$match": {"action": "CAMPAIGN_COMPLETED", "runDate": {"$gte": start_dt, "$lte": end_dt}}},
        {"$group": {"_id": None, "totalSent": {"$sum": "$sentCount"}}},
    ]
    total_sent_result = await logs.aggregate(total_sent_pipeline).to_list(length=1)
    total_sent_emails = total_sent_result[0]["totalSent"] if total_sent_result else 0

    # Top 7 days upload ranking — always fixed to last 7 days regardless of selected range
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7_start = today_start - timedelta(days=6)
    last_7_match = {"createdAt": {"$gte": last_7_start, "$lte": now}}
    top_7_pipeline = [
        {"$match": last_7_match},
        {"$group": {"_id": "$employeeId", "uploadedCount": {"$sum": 1}}},
        {"$sort": {"uploadedCount": -1}},
        {"$limit": 10},
    ]
    top_7_rows = await emails.aggregate(top_7_pipeline).to_list(length=10)
    top_7_days_upload_ranking = []
    for row in top_7_rows:
        emp_id = row["_id"]
        employee_doc = await employees.find_one({"_id": _safe_object_id(emp_id)})
        emp_name = None
        if employee_doc:
            user = await get_collection("users").find_one({"_id": _safe_object_id(employee_doc["userId"])})
            emp_name = user["name"] if user else None
        top_7_days_upload_ranking.append({
            "employeeId": emp_id,
            "employeeName": emp_name or "Unknown",
            "uploadedCount": row["uploadedCount"],
        })

    return {
        "totalEmployees": total_employees,
        "totalUploads": total_uploads,
        "totalUniqueEmails": total_unique_emails,
        "totalSentEmails": total_sent_emails,
        "employeeRanking": employee_ranking,
        "top7DaysUploadRanking": top_7_days_upload_ranking,
        "employeeStatistics": employee_statistics,
        "recentActivities": recent_activities,
        "profileUsage": profile_usage,
    }


def _safe_object_id(id_str: str):
    from bson import ObjectId

    return ObjectId(id_str) if ObjectId.is_valid(id_str) else None
