from datetime import datetime, timezone

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.database.mongodb import get_collection
from app.profiles.model import MAX_PROFILES_PER_EMPLOYEE, build_profile_document
from app.profiles.schema import ProfileCreate, ProfileUpdate
from app.utils.response import serialize_doc, to_object_id
from app.notifications.service import create_notification
from app.notifications.schema import NotificationType

COLLECTION = "profiles"


async def _assert_owns_profile_or_admin(profile: dict, employee_id: str, is_admin: bool) -> None:
    if not is_admin and profile["employeeId"] != employee_id:
        raise ForbiddenException("You do not have access to this profile")


async def create_profile(employee_id: str, payload: ProfileCreate) -> dict:
    profiles = get_collection(COLLECTION)

    count = await profiles.count_documents({"employeeId": employee_id})
    if count >= MAX_PROFILES_PER_EMPLOYEE:
        raise BadRequestException(
            f"Maximum of {MAX_PROFILES_PER_EMPLOYEE} profiles allowed per employee"
        )

    existing = await profiles.find_one({"employeeId": employee_id, "profileName": payload.profileName})
    if existing:
        raise ConflictException("A profile with this name already exists for this employee")

    doc = build_profile_document(
        employee_id=employee_id,
        profile_name=payload.profileName,
        gmail_account=str(payload.gmailAccount),
        options=payload.options.model_dump(),
    )
    result = await profiles.insert_one(doc)
    created = await profiles.find_one({"_id": result.inserted_id})

    await create_notification(
        employee_id=employee_id,
        message=f"New profile '{payload.profileName}' was created successfully.",
        type=NotificationType.INFO,
    )

    return serialize_doc(created)


async def list_profiles(employee_id: str | None) -> list[dict]:
    profiles = get_collection(COLLECTION)
    query = {"employeeId": employee_id} if employee_id else {}
    cursor = profiles.find(query)
    return [serialize_doc(d) async for d in cursor]


async def get_profile(profile_id: str, employee_id: str, is_admin: bool) -> dict:
    profiles = get_collection(COLLECTION)
    doc = await profiles.find_one({"_id": to_object_id(profile_id)})
    if not doc:
        raise NotFoundException("Profile not found")
    doc = serialize_doc(doc)
    await _assert_owns_profile_or_admin(doc, employee_id, is_admin)
    return doc


async def update_profile(profile_id: str, employee_id: str, is_admin: bool, payload: ProfileUpdate) -> dict:
    profiles = get_collection(COLLECTION)
    existing = await profiles.find_one({"_id": to_object_id(profile_id)})
    if not existing:
        raise NotFoundException("Profile not found")
    await _assert_owns_profile_or_admin(serialize_doc(existing), employee_id, is_admin)

    update_data = payload.model_dump(exclude_unset=True)
    if "options" in update_data and update_data["options"] is not None:
        update_data["options"] = update_data["options"]
    update_data = {k: v for k, v in update_data.items() if v is not None}
    if not update_data:
        return serialize_doc(existing)

    update_data["updatedAt"] = datetime.now(timezone.utc)
    result = await profiles.find_one_and_update(
        {"_id": to_object_id(profile_id)}, {"$set": update_data}, return_document=True
    )
    return serialize_doc(result)


async def set_active_status(profile_id: str, employee_id: str, is_admin: bool, is_active: bool) -> dict:
    profiles = get_collection(COLLECTION)
    existing = await profiles.find_one({"_id": to_object_id(profile_id)})
    if not existing:
        raise NotFoundException("Profile not found")
    await _assert_owns_profile_or_admin(serialize_doc(existing), employee_id, is_admin)

    result = await profiles.find_one_and_update(
        {"_id": to_object_id(profile_id)},
        {"$set": {"isActive": is_active, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True,
    )
    return serialize_doc(result)


async def delete_profile(profile_id: str, employee_id: str, is_admin: bool) -> None:
    profiles = get_collection(COLLECTION)
    existing = await profiles.find_one({"_id": to_object_id(profile_id)})
    if not existing:
        raise NotFoundException("Profile not found")
    await _assert_owns_profile_or_admin(serialize_doc(existing), employee_id, is_admin)
    await profiles.delete_one({"_id": to_object_id(profile_id)})
