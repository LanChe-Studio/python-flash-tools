import os
import platform
from abc import ABC, abstractmethod


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def runnable_files(self) -> dict[str, list[str]]:
        pass

    @property
    @abstractmethod
    def mirrors(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def common_paths(self) -> dict[str, list[str]]:
        pass

    def __init__(self, path: str = None) -> None:
        self._path = path


    def get_mirrors(self, system: str = None) -> list[str]:
        if system is None:
            system = platform.system().lower()
        return [mirror.replace("{system}", system) for mirror in self.mirrors]


    def get_path(self):
        if self._path is None:
            return os.path.join("tools", self.name)
        return self._path


    def set_path(self, path: str):
        self._path = path


    def get_runnable_files(self, system: str = None) -> list[str]:
        if system is None:
            system = platform.system().lower()
        if not self.runnable_files:
            return []
        return self.runnable_files.get(system, [])


    def get_common_paths(self, system: str = None) -> list[str]:
        if system is None:
            system = platform.system().lower()
        return self.common_paths.get(system, [])


    def find_available(self, system: str = None) -> list[str]:
        if system is None:
            system = platform.system().lower()
        available = []
        for path in self.get_common_paths(system) + [os.path.join(self.get_path())]:
            if self.is_available(system, path):
                available.append(path)
        return available


    @abstractmethod
    def is_available(self, system: str = None, path: str = None) -> bool:
        pass


    def change_path_to_available(self) -> bool:
        if self.is_available():
            return True
        available_paths = self.find_available()

        if not available_paths:
            return False

        self.set_path(available_paths[0])
        return True

