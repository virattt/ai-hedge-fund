"""Model aggregator — importing this package registers every observing-pool
table on the shared ``Base`` (PRD v4 §8.1 / F1 model-discovery pattern).

Both the ``create_all`` site (``app/backend/main.py``) and Alembic's ``env.py``
import this so SQLAlchemy sees the tables. Without it, the first refresh would
write to non-existent tables. New model modules must be imported here.
"""

from src.storage.database import Base
from src.storage.models.observing_pools import (
    CandidateSecurity,
    InnovationPlatform,
    ObservationPoolEntry,
    PoolEntryStatus,
    PoolRefreshRun,
    RefreshRunStatus,
)
from src.storage.models.serenity import (
    EvidenceGrade,
    EvidenceReference,
    RecommendedAction,
    SerenityResearchRecord,
    SourceType,
)
from src.storage.models.monitoring import (
    Granularity,
    MonitorConfig,
    OpportunityReport,
    ReportLabel,
)

__all__ = [
    "Base",
    "CandidateSecurity",
    "InnovationPlatform",
    "ObservationPoolEntry",
    "PoolEntryStatus",
    "PoolRefreshRun",
    "RefreshRunStatus",
    "EvidenceGrade",
    "EvidenceReference",
    "RecommendedAction",
    "SerenityResearchRecord",
    "SourceType",
    "Granularity",
    "MonitorConfig",
    "OpportunityReport",
    "ReportLabel",
]
