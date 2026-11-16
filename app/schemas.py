from typing import Any, Literal
from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw unstructured text")
    fields: list[str] = Field(default_factory=list, description="Optional custom fields to pull out")
    mode: Literal["auto", "rules", "llm"] = "auto"


class ExportRequest(BaseModel):
    result: dict[str, Any]
    format: Literal["json", "csv", "md"] = "json"
