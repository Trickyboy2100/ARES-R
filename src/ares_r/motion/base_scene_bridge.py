"""AMR lifecycle bridge that invalidates LocalScene below task code."""

from __future__ import annotations


class SceneAwareBase:
    """Transparent AMR decorator with mandatory scene lifecycle callbacks."""

    def __init__(self, base, local_scene):
        self._base = base
        self._scene = local_scene

    def _motion(self, operation, *args, **kwargs):
        self._scene.base_motion_started()
        try:
            result = operation(*args, **kwargs)
        except Exception:
            self._scene.invalidate("BASE_MOTION_ERROR")
            raise
        self._scene.base_settled()
        return result

    def move_position(self, *args, **kwargs):
        return self._motion(self._base.move_position, *args, **kwargs)

    def move_relative(self, *args, **kwargs):
        return self._motion(self._base.move_relative, *args, **kwargs)

    def navigate(self, *args, **kwargs):
        return self._motion(self._base.navigate, *args, **kwargs)

    def run_task(self, *args, **kwargs):
        return self._motion(self._base.run_task, *args, **kwargs)

    def stop(self):
        result = self._base.stop()
        self._scene.base_settled()
        return result

    def __getattr__(self, name):
        return getattr(self._base, name)

