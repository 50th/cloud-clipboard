"""模型包：导入所有模型以注册到 `Base.metadata`（Alembic autogenerate 依赖它）。"""

from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.clipboard import ClipboardItem
from app.db.models.invite_code import InviteCode
from app.db.models.user import User

__all__ = ["AdminAuditLog", "ClipboardItem", "InviteCode", "User"]
