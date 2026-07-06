from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUser, get_current_user, verify_n8n_api_key
from app.employees.service import get_employee_by_user_id
from app.logs import service
from app.logs.schema import CampaignLogUpdate
from app.schemas.common import ApiResponse, PaginationParams
from app.utils.pagination import pagination_params

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=ApiResponse)
async def list_logs(
    employeeId: str | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role == "admin":
        target_employee_id = employeeId
    else:
        employee = await get_employee_by_user_id(current_user.user_id)
        target_employee_id = employee["id"]

    result = await service.list_logs(target_employee_id, params)
    return ApiResponse(message="Logs fetched", data=result)


@router.post("/campaign", response_model=ApiResponse, dependencies=[Depends(verify_n8n_api_key)])
async def campaign_log_update(payload: CampaignLogUpdate):
    """Webhook endpoint n8n calls after a campaign finishes sending."""
    log = await service.record_campaign_completion(payload)
    return ApiResponse(message="Campaign log recorded", data=log)
