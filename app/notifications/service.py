from app.core.exceptions import NotFoundException
from app.database.mongodb import get_collection
from app.notifications.model import build_notification_document
from app.notifications.schema import NotificationType
from app.notifications.stream import broadcast
from app.utils.response import serialize_doc, serialize_list, to_object_id

COLLECTION = "notifications"


async def create_notification(employee_id: str, message: str, type: NotificationType) -> dict:
    notifications = get_collection(COLLECTION)
    doc = build_notification_document(employee_id, message, type)
    result = await notifications.insert_one(doc)
    created = await notifications.find_one({"_id": result.inserted_id})
    notification = serialize_doc(created)
    # Push live to any connected SSE clients
    await broadcast(employee_id, notification)
    return notification


async def list_notifications(employee_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
    notifications = get_collection(COLLECTION)
    query: dict = {"employeeId": employee_id}
    if unread_only:
        query["isRead"] = False

    cursor = notifications.find(query).sort("createdAt", -1).limit(limit)
    return serialize_list([d async for d in cursor])


async def mark_as_read(notification_id: str, employee_id: str) -> dict:
    notifications = get_collection(COLLECTION)
    result = await notifications.find_one_and_update(
        {"_id": to_object_id(notification_id), "employeeId": employee_id},
        {"$set": {"isRead": True}},
        return_document=True,
    )
    if not result:
        raise NotFoundException("Notification not found")
    return serialize_doc(result)


async def mark_all_as_read(employee_id: str) -> dict:
    notifications = get_collection(COLLECTION)
    result = await notifications.update_many(
        {"employeeId": employee_id, "isRead": False},
        {"$set": {"isRead": True}}
    )
    return {"modifiedCount": result.modified_count}
