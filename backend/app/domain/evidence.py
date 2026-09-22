from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json

from pydantic import BaseModel, Field


class EvidenceArtifact(BaseModel):
    artifact_type: str
    uri: str
    sha256: str
    size_bytes: int


class EvidenceManifest(BaseModel):
    product: str = "Cluster Assurance Orchestrator"
    product_version: str
    profile_version: str
    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result_summary: dict[str, object]
    artifacts: list[EvidenceArtifact] = Field(default_factory=list)

    def stable_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"generated_at"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()


def hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()

