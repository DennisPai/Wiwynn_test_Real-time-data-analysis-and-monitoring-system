from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AnyRole, get_current_user, get_db, require_role
from app.models.user import Role, User
from app.schemas.data_record import (
    BulkImportError,
    BulkImportResponse,
    DataCreate,
    DataRecordResponse,
    DataUpdate,
)
from app.schemas.user import PaginatedResponse
from app.services import data_service
from app.utils.csv_importer import parse_csv, parse_json

router = APIRouter(prefix="/data", tags=["data"])


async def _resolve_owner_id(
    db: AsyncSession,
    row: DataCreate,
    current_user: User,
) -> int | HTTPException:
    """
    Resolve owner_id for a bulk-import row.
    - If owner_email is absent → use current_user.id
    - If owner_email is present and current_user is not admin → HTTPException 403
    - If owner_email is present, admin, and email doesn't exist → HTTPException 422
    - If owner_email is present and admin → lookup and return target user id

    Returns int (owner_id) on success, HTTPException on error.
    """
    owner_email = getattr(row, "owner_email", None)
    if not owner_email:
        return current_user.id

    # owner_email provided
    if current_user.role != Role.admin:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有 admin 可在 CSV 內指定 owner_email 跨 owner 匯入",
        )

    # admin lookup
    result = await db.execute(select(User).where(User.email == owner_email))
    target = result.scalar_one_or_none()
    if target is None:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"owner_email={owner_email!r} 不存在於 users 表",
        )
    return target.id

# T5.1: wide schema 排序欄位白名單（防止 SQL injection）
_VALID_SORT_FIELDS = {
    "ts",
    "created_at",
    "updated_at",
    "temperature",
    "humidity",
    "pressure",
    "voltage",
    "cpu_usage",
}
_VALID_SORT_ORDERS = {"asc", "desc"}

# bulk-import 大檔上限（10 MB）
_MAX_UPLOAD_SIZE = 10_000_000


@router.get("", response_model=PaginatedResponse[DataRecordResponse])
async def list_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
    page: int = Query(1, ge=1, description="頁碼（起始 1）"),
    size: int = Query(20, ge=1, le=100, description="每頁筆數（最大 100）"),
    # T5.1: 新增 wide schema query params
    sources: list[str] | None = Query(None, description="來源過濾（user / simulator）"),
    metric: str | None = Query(None, description="單一 metric range filter 欄位名稱"),
    min_value: Decimal | None = Query(None, description="metric 最小值"),
    max_value: Decimal | None = Query(None, description="metric 最大值"),
    # 保留通用 query params
    owner_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort_by: str = Query("ts", description="排序欄位"),
    sort_order: str = Query("desc", description="asc 或 desc"),
) -> PaginatedResponse[DataRecordResponse]:
    """列出資料記錄（任何已登入角色可讀）。wide schema。"""
    # T5.1: 排序欄位白名單驗證（wide schema）
    if sort_by not in _VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"sort_by 不在允許清單：{sorted(_VALID_SORT_FIELDS)}",
        )
    if sort_order not in _VALID_SORT_ORDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="sort_order 只接受 asc 或 desc",
        )

    result = await data_service.list_records(
        db,
        page=page,
        size=size,
        sources=sources,
        metric=metric,
        min_value=min_value,
        max_value=max_value,
        owner_id=owner_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedResponse[DataRecordResponse](**result)


@router.post(
    "/bulk-import",
    response_model=BulkImportResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_import(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, require_role(Role.admin, Role.user)],
    file: UploadFile = File(...),
) -> BulkImportResponse:
    """
    批量導入 CSV 或 JSON 檔案（admin/user 可用）。wide format。
    - 檔案大小限制 10 MB，超過回 413
    - header 偵測：舊 long 格式 / 缺所有 metric → 整檔拒絕
    - per-row 逐行驗證，部分失敗仍插入有效列
    - 回傳 {inserted, failed, errors:[{row, reason, missing_columns}]}
    """
    # 讀取並驗證檔案大小
    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="檔案超過 10 MB 上限",
        )

    # 依副檔名決定解析方式
    filename = file.filename or ""
    if filename.lower().endswith(".json"):
        valid_rows, errors = parse_json(content)
    else:
        # 預設當 CSV 處理
        valid_rows, errors = parse_csv(content)

    # 批量寫入有效列（T5.2: 使用 wide DataCreate + 自動計算 anomaly_flags）
    # Fix 2: owner_email → owner_id lookup（admin 模式允許跨 owner）
    inserted = 0
    for row_index, row in enumerate(valid_rows):
        owner_id_or_exc = await _resolve_owner_id(db, row, current_user)
        if isinstance(owner_id_or_exc, HTTPException):
            # 以 BulkImportError 格式回傳，繼續處理其他 row
            errors.append(
                BulkImportError(
                    row=row_index + 1,
                    reason=owner_id_or_exc.detail,
                )
            )
            continue
        await data_service.create_record(db, row, owner_id=owner_id_or_exc)
        inserted += 1

    return BulkImportResponse(
        inserted=inserted,
        failed=len(errors),
        errors=errors,
    )


@router.post("", response_model=DataRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_data(
    body: DataCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, require_role(Role.admin, Role.user)],
) -> DataRecordResponse:
    """新增資料記錄（admin/user 可用）。T5.2: wide DataCreate + 自動 anomaly_flags。"""
    record = await data_service.create_record(db, body, owner_id=current_user.id)
    return DataRecordResponse.model_validate(record)


@router.get("/{record_id}", response_model=DataRecordResponse)
async def get_data(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyRole],
) -> DataRecordResponse:
    """取得單筆資料記錄（任何已登入角色可讀）。T5.3: wide response。"""
    record = await data_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="記錄不存在")
    return DataRecordResponse.model_validate(record)


@router.patch("/{record_id}", response_model=DataRecordResponse)
async def update_data(
    record_id: int,
    body: DataUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DataRecordResponse:
    """
    更新資料記錄。T5.3: wide DataUpdate + wide response。
    - admin：可更新任何人的記錄
    - user：只能更新自己的記錄
    - viewer：403
    """
    record = await data_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="記錄不存在")

    if not data_service.check_can_modify(record, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="權限不足")

    updated = await data_service.update_record(db, record, body, current_user)
    return DataRecordResponse.model_validate(updated)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_data(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """
    刪除資料記錄。T5.3: 邏輯不變。
    - admin：可刪除任何人的記錄
    - user：只能刪除自己的記錄
    - viewer：403
    """
    record = await data_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="記錄不存在")

    if not data_service.check_can_modify(record, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="權限不足")

    await data_service.delete_record(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
