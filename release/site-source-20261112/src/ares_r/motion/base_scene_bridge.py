"""AMR lifecycle bridge that invalidates LocalScene below task code."""

from __future__ import annotations


class SceneAwareBase:
    """Transparent AMR decorator with mandatory scene lifecycle callbacks."""

    def __init__(self, base, local_scene, completion_observer=None):
        self._base = base
        self._scene = local_scene
        self._completion = completion_observer
        self.last_completion = None

    def _motion(self, operation, *args, **kwargs):
        baseline = self._completion.capture() if self._completion is not None else None
        self._scene.base_motion_started()
        try:
            result = operation(*args, **kwargs)
            if self._completion is None:
                raise RuntimeError("asynchronous AMR motion requires BaseMotionObserver")
            expected_translation = 0.0
            expected_yaw = 0.0
            if getattr(operation, "__name__", "") == "move_relative" and len(args) >= 3:
                expected_translation = (float(args[0]) ** 2 + float(args[1]) ** 2) ** 0.5
                expected_yaw = float(args[2])
            timeout = kwargs.get("timeout_s")
            if timeout is None and len(args) >= 6:
                timeout = args[5]
            self.last_completion = self._completion.wait(
                baseline, timeout_s=timeout,
                expected_translation_m=expected_translation,
                expected_yaw_deg=expected_yaw)
        except Exception:
            self._scene.invalidate("BASE_MOTION_ERROR")
            try:
                self._base.stop()
            except Exception:
                pass
            raise
        self._scene.base_settled()
        if isinstance(result, dict):
            result = dict(result)
            result["completion"] = self.last_completion
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
