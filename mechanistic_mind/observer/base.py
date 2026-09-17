from abc import ABC, abstractmethod
from typing import Any


class Observer(ABC):
    """Passive simulation observer contract."""

    @abstractmethod
    def on_run_start(self, metadata: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_step(self, result: Any) -> None:
        raise NotImplementedError

    def on_reset(self, metadata: Any) -> None:
        """Default reset behavior starts a fresh observation run."""
        self.on_run_start(metadata)
