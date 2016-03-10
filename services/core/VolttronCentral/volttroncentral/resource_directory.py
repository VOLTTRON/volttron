from .registry import PlatformRegistry


class ResourceDirectory:
    def __init__(self):
        self._registry = PlatformRegistry()

    @property
    def platform_registry(self):
        return self._registry
