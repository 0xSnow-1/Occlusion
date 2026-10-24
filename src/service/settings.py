"""Runtime configuration for the Occlusion HTTP service."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_COLLECTION = "occlusion"
DEFAULT_QDRANT_PATH = "./data/qdrant_storage"
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_REQUEST_TIMEOUT_S = 30.0
DEFAULT_MAX_QUESTION_LENGTH = 1000
DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_REGION = "us-east-1"


@dataclass(frozen=True)
class Settings:
    """Service settings, sourced from the environment at startup."""

    collection_name: str = DEFAULT_COLLECTION
    qdrant_path: str = DEFAULT_QDRANT_PATH
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S
    max_question_length: int = DEFAULT_MAX_QUESTION_LENGTH
    bedrock_model_id: str = DEFAULT_MODEL_ID
    bedrock_region: str = DEFAULT_REGION

    def __post_init__(self) -> None:
        if not self.collection_name.strip():
            raise ValueError("collection_name must not be blank")
        if not self.qdrant_path.strip():
            raise ValueError("qdrant_path must not be blank")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if self.request_timeout_s <= 0:
            raise ValueError("request_timeout_s must be positive")
        if self.max_question_length <= 0:
            raise ValueError("max_question_length must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            collection_name=os.getenv("OCCLUSION_COLLECTION", DEFAULT_COLLECTION),
            qdrant_path=os.getenv("OCCLUSION_QDRANT_PATH", DEFAULT_QDRANT_PATH),
            confidence_threshold=float(
                os.getenv(
                    "OCCLUSION_CONFIDENCE_THRESHOLD",
                    str(DEFAULT_CONFIDENCE_THRESHOLD),
                )
            ),
            request_timeout_s=float(
                os.getenv("OCCLUSION_REQUEST_TIMEOUT_S", str(DEFAULT_REQUEST_TIMEOUT_S))
            ),
            max_question_length=int(
                os.getenv(
                    "OCCLUSION_MAX_QUESTION_LENGTH",
                    str(DEFAULT_MAX_QUESTION_LENGTH),
                )
            ),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
            bedrock_region=os.getenv("BEDROCK_REGION", DEFAULT_REGION),
        )


__all__ = ["Settings"]
