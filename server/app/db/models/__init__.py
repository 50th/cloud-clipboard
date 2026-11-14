"""模型包：导入所有模型以注册到 `Base.metadata`（Alembic autogenerate 依赖它）。"""

from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.clipboard import ClipboardItem
from app.db.models.invite_code import InviteCode
from app.db.models.share import ClipboardShare
from app.db.models.share_access_log import ShareAccessLog
from app.db.models.share_setting import ShareSetting
from app.db.models.user import User

__all__ = [
    "AdminAuditLog",
    "ClipboardItem",
    "ClipboardShare",
    "InviteCode",
    "ShareAccessLog",
    "ShareSetting",
    "User",
]
