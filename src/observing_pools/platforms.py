"""The five disruptive-innovation platforms (ARK / Cathie-Wood thesis).

Single source of truth for the platform taxonomy: keys, display names, the
investment description, and the deterministic keyword seeds used by the
classifier (``classify.py``). ``init_platforms`` upserts these into the
``innovation_platforms`` table idempotently.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.storage.models import InnovationPlatform


@dataclass(frozen=True)
class PlatformDef:
    key: str
    name: str
    description: str
    keywords: tuple[str, ...]


PLATFORMS: tuple[PlatformDef, ...] = (
    PlatformDef(
        key="ai",
        name="Artificial Intelligence",
        description="The primary catalyst for the most significant technological disruption in history.",
        keywords=(
            "artificial intelligence",
            "ai",
            "machine learning",
            "deep learning",
            "neural",
            "gpu",
            "accelerator",
            "data center",
            "datacenter",
            "cloud",
            "semiconductor",
            "chip",
            "foundry",
            "llm",
            "inference",
            "software",
            "analytics",
        ),
    ),
    PlatformDef(
        key="robotics",
        name="Robotics",
        description="Autonomous mobility and high-dexterity humanoid robots.",
        keywords=(
            "robot",
            "robotics",
            "automation",
            "autonomous",
            "humanoid",
            "actuator",
            "sensor",
            "drone",
            "lidar",
            "self-driving",
            "fsd",
            "machine vision",
            "evtol",
        ),
    ),
    PlatformDef(
        key="energy_storage",
        name="Energy Storage",
        description="Battery technology essential to autonomous transport and robotic labor.",
        keywords=(
            "battery",
            "batteries",
            "energy storage",
            "lithium",
            "cell",
            "ev",
            "electric vehicle",
            "grid storage",
            "cathode",
            "anode",
            "solid-state",
        ),
    ),
    PlatformDef(
        key="blockchain",
        name="Blockchain Technology",
        description="The foundation of a rules-based financial internet and digital-asset ecosystem.",
        keywords=(
            "blockchain",
            "bitcoin",
            "crypto",
            "cryptocurrency",
            "digital asset",
            "exchange",
            "stablecoin",
            "mining",
            "miner",
            "wallet",
            "ledger",
            "web3",
        ),
    ),
    PlatformDef(
        key="multiomic_sequencing",
        name="Multiomic Sequencing",
        description="Advanced life sciences (DNA/RNA/protein sequencing) enabling the shift from treatment to cures.",
        keywords=(
            "genomic",
            "genomics",
            "sequencing",
            "dna",
            "rna",
            "protein",
            "crispr",
            "gene editing",
            "gene therapy",
            "diagnostic",
            "life science",
            "biotech",
            "multiomic",
        ),
    ),
)

PLATFORM_KEYS: tuple[str, ...] = tuple(p.key for p in PLATFORMS)
PLATFORM_BY_KEY: dict[str, PlatformDef] = {p.key: p for p in PLATFORMS}


def init_platforms(session: Session) -> list[InnovationPlatform]:
    """Idempotently upsert the five platforms. Safe to call repeatedly."""
    rows: list[InnovationPlatform] = []
    for p in PLATFORMS:
        existing = session.query(InnovationPlatform).filter_by(key=p.key).one_or_none()
        if existing is None:
            existing = InnovationPlatform(key=p.key)
            session.add(existing)
        existing.name = p.name
        existing.description = p.description
        existing.keywords = list(p.keywords)
        existing.enabled = True
        rows.append(existing)
    session.flush()
    return rows
