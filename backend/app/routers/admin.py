"""Admin-only operational endpoints (backup visibility, etc.)."""
from fastapi import APIRouter, Depends

from ..core.config import settings
from ..models.user import User, Role
from ..deps import require_role
from ..services.backups import backup_status

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/backups")
def backups(_: User = Depends(require_role(Role.admin))):
    """Latest database-backup status: age, size and a staleness flag.

    Reads the bind-mounted backup directory (see docker-compose.yml). Reports
    configured=False when there is no backup directory (e.g. local dev).
    """
    return backup_status(settings.backup_dir, settings.backup_stale_hours)
