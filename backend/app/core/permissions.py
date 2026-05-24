from __future__ import annotations

from app.models.user import Role

# 角色階層：數值越大，權限越高
_ROLE_LEVEL: dict[Role, int] = {
    Role.viewer: 0,
    Role.user: 1,
    Role.admin: 2,
}


def role_level(role: Role) -> int:
    """回傳角色數值，用於比較。"""
    return _ROLE_LEVEL.get(role, -1)


def has_role(user_role: Role, required: Role) -> bool:
    """使用者角色是否 >= 所需角色。"""
    return role_level(user_role) >= role_level(required)


def is_admin(user_role: Role) -> bool:
    return user_role == Role.admin


def can_write_data(user_role: Role) -> bool:
    """admin 或 user 可新增/批量匯入資料。"""
    return user_role in (Role.admin, Role.user)


def can_modify_data(user_role: Role, resource_owner_id: int, requester_id: int) -> bool:
    """admin 可改任何人；user 只能改自己；viewer 不能改。"""
    if user_role == Role.admin:
        return True
    if user_role == Role.user and resource_owner_id == requester_id:
        return True
    return False
