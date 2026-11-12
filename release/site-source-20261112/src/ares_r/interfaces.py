"""Hardware-independent interfaces used by the task layer."""

from abc import ABC, abstractmethod
from typing import Optional, Sequence
from .models import DetectionResult, DeviceState, Pose


class Perception(ABC):
    @abstractmethod
    def detect_pick(self) -> DetectionResult: ...

    @abstractmethod
    def detect_place(self, dock_id: int) -> DetectionResult: ...

    @abstractmethod
    def state(self) -> DeviceState: ...

    def probe(self) -> DeviceState:
        """Check availability without triggering a detection."""
        return self.state()

    def close(self) -> None:
        pass


class Arm(ABC):
    @abstractmethod
    def move_to_pose(self, pose: Pose) -> None: ...

    @abstractmethod
    def move_linear_tool(self, distance_m: float) -> None: ...

    @abstractmethod
    def move_named(self, name: str) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def state(self) -> DeviceState: ...


class Gripper(ABC):
    @abstractmethod
    def move_to(self, position: int) -> None: ...

    @abstractmethod
    def position(self) -> int: ...

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def has_object(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def state(self) -> DeviceState: ...


class MobileBase(ABC):
    @abstractmethod
    def navigate(self, station: str) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def station(self) -> Optional[str]: ...

    @abstractmethod
    def state(self) -> DeviceState: ...
