"""Vision result model with cost/usage awareness."""
import time


class VisionResult:
    """Represents the result of a vision task."""

    def __init__(self, text: str, model: str, task: str, metadata: dict | None = None):
        self.text = text
        self.model = model
        self.task = task
        self.metadata = metadata or {}
        self.duration = self.metadata.get("duration", 0)
        self.prompt_tokens = self.metadata.get("prompt_tokens", 0)
        self.completion_tokens = self.metadata.get("completion_tokens", 0)

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    def __repr__(self):
        return (f"VisionResult(task={self.task}, model={self.model}, "
                f"tokens={self.total_tokens}, duration={self.duration}s)")
