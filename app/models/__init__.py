"""
Models package
"""
from app.models.spool import Spool, SpoolCreateSchema, SpoolUpdateSchema, SpoolReadSchema
from app.models.material import Material
from app.models.job import Job
from app.models.printer import Printer
from app.models.settings import Setting
from app.models.weight_history import WeightHistory, WeightHistoryCreate, WeightHistoryRead
from app.models.bambu_cloud_config import (
    BambuCloudConfig,
    BambuCloudConfigCreate,
    BambuCloudConfigRead,
    BambuCloudSyncStatus,
)
from app.models.cloud_conflict import (
    CloudConflict,
    CloudConflictCreate,
    CloudConflictRead,
    CloudConflictResolve,
)

__all__ = [
    "Spool",
    "SpoolCreateSchema",
    "SpoolUpdateSchema",
    "SpoolReadSchema",
    "Material",
    "Job",
    "Printer",
    "Setting",
    "WeightHistory",
    "WeightHistoryCreate",
    "WeightHistoryRead",
    # Bambu Cloud Integration
    "BambuCloudConfig",
    "BambuCloudConfigCreate",
    "BambuCloudConfigRead",
    "BambuCloudSyncStatus",
    "CloudConflict",
    "CloudConflictCreate",
    "CloudConflictRead",
    "CloudConflictResolve",
]
