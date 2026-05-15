from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


class AIAnalysisLog(Base):
    __tablename__ = "ai_analysis_log"

    # ------------------------------------------------------------------ #
    # Primary key                                                          #
    # ------------------------------------------------------------------ #
    log_id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Foreign key                                                          #
    # Every log entry belongs to exactly one submission.                  #
    # A submission can have multiple log entries (one per pipeline phase). #
    # ------------------------------------------------------------------ #
    submission_id = Column(
        Integer,
        ForeignKey("submissions.submission_id"),
        nullable=False
    )

    # ------------------------------------------------------------------ #
    # Pipeline step identification                                         #
    # ------------------------------------------------------------------ #
    step_name     = Column(String, nullable=False)   # "identification" | "extraction" | ...
    model_version = Column(String, nullable=False)   # "gemini-1.5-flash"

    # ------------------------------------------------------------------ #
    # The full conversation with Gemini for this step                     #
    # Stored as TEXT (not VARCHAR) — prompts can be long.                 #
    # ------------------------------------------------------------------ #
    raw_response = Column(Text, nullable=False)

    # ------------------------------------------------------------------ #
    # Parsed and validated result                                          #
    # JSONB gives us:                                                      #
    #   - binary storage (faster than TEXT JSON in Postgres)              #
    #   - ability to index and query inside the JSON                      #
    #   - validation that the value is valid JSON                         #
    # NULL means Pydantic validation failed on this response.             #
    # ------------------------------------------------------------------ #
    parsed_result = Column(JSONB, nullable=True)

    # ------------------------------------------------------------------ #
    # Outcome metadata                                                     #
    # ------------------------------------------------------------------ #
    confidence = Column(Float, nullable=True)   # top-level score from Gemini
    success    = Column(Boolean, nullable=False, default=False)

    # ------------------------------------------------------------------ #
    # Timestamp                                                            #
    # ------------------------------------------------------------------ #
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    submission = relationship("Submission", back_populates="ai_logs")

    def __repr__(self) -> str:
        return (
            f"<AIAnalysisLog id={self.log_id} "
            f"submission={self.submission_id} "
            f"step={self.step_name} "
            f"success={self.success}>"
        )