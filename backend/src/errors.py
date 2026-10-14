from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class AppError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def invalid(code: str, message: str, **details: Any) -> AppError:
    return AppError(code=code, message=message, details=details)

