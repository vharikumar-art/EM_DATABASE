import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.employees.service import get_employee_by_user_id
from app.notifications import service, stream
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


async def _resolve_employee_id(current_user: CurrentUser, employee_id_query: str | None) -> str:
    if current_user.role == "admin":
        # If an admin provides an employeeId, view that employee's notifications.
        # Otherwise, default to the admin's own user_id.
        return employee_id_query or current_user.user_id
    
    employee = await get_employee_by_user_id(current_user.user_id)
    return employee["id"]


@router.get("/stream")
async def notifications_stream(token: str = Query(...)):
    """
    SSE endpoint for live notifications.
    The browser's EventSource API cannot send custom headers,
    so the JWT access token is passed as a query parameter.
    """
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise UnauthorizedException(str(exc)) from exc

    if payload.get("type") != "access":
        raise UnauthorizedException("Provide an access token")

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise UnauthorizedException("Malformed token payload")

    current_user = CurrentUser(user_id=user_id, role=role)

    # For employees, scope to their own record; admins stream all (by convention use their userId)
    if role == "admin":
        employee_id = user_id
    else:
        employee = await get_employee_by_user_id(user_id)
        employee_id = employee["id"]

    q = stream.subscribe(employee_id)

    async def event_generator():
        try:
            # Send a ping immediately so the browser knows the connection is alive
            yield "event: ping\ndata: connected\n\n"
            while True:
                try:
                    notification = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(notification)}\n\n"
                except asyncio.TimeoutError:
                    # Send a keepalive comment every 30s to prevent connection drop
                    yield ": keepalive\n\n"
        finally:
            stream.unsubscribe(employee_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables nginx buffering
        },
    )


@router.get("", response_model=ApiResponse)
async def list_notifications(
    employeeId: str | None = Query(default=None),
    unreadOnly: bool = Query(default=False),
    limit: int = Query(default=50),
    current_user: CurrentUser = Depends(get_current_user),
):
    employee_id = await _resolve_employee_id(current_user, employeeId)
    notifications = await service.list_notifications(employee_id, unreadOnly, limit)
    return ApiResponse(message="Notifications fetched", data=notifications)


@router.patch("/read-all", response_model=ApiResponse)
async def mark_all_as_read(
    employeeId: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    employee_id = await _resolve_employee_id(current_user, employeeId)
    result = await service.mark_all_as_read(employee_id)
    return ApiResponse(message="All notifications marked as read", data=result)


@router.patch("/{notification_id}/read", response_model=ApiResponse)
async def mark_as_read(
    notification_id: str,
    employeeId: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    employee_id = await _resolve_employee_id(current_user, employeeId)
    notification = await service.mark_as_read(notification_id, employee_id)
    return ApiResponse(message="Notification marked as read", data=notification)
