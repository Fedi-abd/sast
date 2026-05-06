from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolRunResult:
    success: bool
    raw_output: str
    error_message: Optional[str] = None
    exit_code: int = 0

class ToolAdapter(ABC):
    @abstractmethod
    def run(self, repo_path: str, config: dict) -> ToolRunResult:
        """Run the tool and return results"""
        pass
