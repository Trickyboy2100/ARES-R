"""Native Open3D live viewer with independently scheduled camera scans.

The GUI retains the last complete cloud while the camera worker acquires the
next one.  This is a raw BODY-cloud viewer only: no self-filter and no planner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import time

from ..perception.body_pointcloud import capture_body_cloud
from .body_cloud_viewer import _open3d_geometry, scene_spec


@dataclass
class ScanSchedule:
    interval_s: float = 2.0
    auto: bool = False
    pending_once: bool = False
    busy: bool = False
    last_started_monotonic: float | None = None
    actual_start_intervals_s: list = field(default_factory=list)

    def set_interval(self, value: float) -> None:
        if not 0.5 <= float(value) <= 3600.0:
            raise ValueError("scan interval must be 0.5..3600 seconds")
        self.interval_s = float(value)

    def request_once(self) -> None:
        self.pending_once = True

    def due(self, now: float) -> bool:
        if self.busy:
            return False
        if self.pending_once:
            return True
        return self.auto and (self.last_started_monotonic is None or
                              now - self.last_started_monotonic >= self.interval_s)

    def started(self, now: float) -> None:
        if self.last_started_monotonic is not None:
            self.actual_start_intervals_s.append(now - self.last_started_monotonic)
        self.last_started_monotonic = now
        self.pending_once = False
        self.busy = True

    def finished(self) -> None:
        self.busy = False


def run_live(config: dict, world_path: Path, crosscheck_path: Path,
             interval_s: float = 2.0, initial_manifest: Path | None = None) -> None:
    """Run native Open3D GUI. Camera acquisition occurs only on its worker."""
    import open3d as o3d
    from open3d.visualization import gui, rendering

    schedule = ScanSchedule(interval_s=float(interval_s))
    stopping = threading.Event()
    schedule_lock = threading.Lock()
    app = gui.Application.instance
    app.initialize()
    window = app.create_window("ARES-R BODY cloud | raw / no self-filter", 1600, 1000)
    widget = gui.SceneWidget()
    widget.scene = rendering.Open3DScene(window.renderer)
    widget.scene.set_background([0.04, 0.05, 0.07, 1.0])
    panel = gui.Vert(8, gui.Margins(12, 12, 12, 12))
    status = gui.Label("Ready; auto scan OFF")
    scan_once = gui.Button("Scan Once")
    auto = gui.Checkbox("Auto scan")
    interval = gui.NumberEdit(gui.NumberEdit.DOUBLE)
    interval.set_limits(0.5, 3600.0)
    interval.double_value = schedule.interval_s
    panel.add_child(gui.Label("Camera interval (seconds)"))
    panel.add_child(interval); panel.add_child(scan_once); panel.add_child(auto)
    panel.add_child(gui.Label("GUI render loop is independent of camera scans."))
    panel.add_child(status)
    window.add_child(widget); window.add_child(panel)

    def layout(context):
        rect = window.content_rect
        panel_width = 360
        widget.frame = gui.Rect(rect.x, rect.y, rect.width - panel_width, rect.height)
        panel.frame = gui.Rect(rect.get_right() - panel_width, rect.y, panel_width, rect.height)

    def load_scene(spec):
        widget.scene.clear_geometry()
        point_material = rendering.MaterialRecord()
        point_material.shader = "defaultUnlit"; point_material.point_size = 2.0
        mesh_material = rendering.MaterialRecord(); mesh_material.shader = "defaultLit"
        for name, geometry in _open3d_geometry(spec):
            widget.scene.add_geometry(name, geometry,
                                      point_material if name == "BODY_POINTCLOUD" else mesh_material)
        bounds = o3d.geometry.AxisAlignedBoundingBox.create_from_points(
            o3d.utility.Vector3dVector(spec["cloud"].points_body_m))
        widget.setup_camera(55.0, bounds, bounds.get_center())
        widget.force_redraw()

    def acquire():
        started = time.monotonic()
        try:
            manifest = capture_body_cloud(config)
            spec = scene_spec(manifest, world_path, crosscheck_path)
            elapsed = time.monotonic() - started
            with schedule_lock:
                schedule.finished()
                observed = (schedule.actual_start_intervals_s[-1]
                            if schedule.actual_start_intervals_s else None)
            def publish_success():
                load_scene(spec)
                status.text = ("Scan %.3fs | actual interval %s | %s" %
                               (elapsed, "n/a" if observed is None else "%.3fs" % observed,
                                Path(manifest).parent.name))
            app.post_to_main_thread(window, publish_success)
        except Exception as exc:
            message = "%s" % exc
            with schedule_lock:
                schedule.finished()
            app.post_to_main_thread(window,
                                    lambda: setattr(status, "text", "Scan failed: %s" % message))

    def scheduler_loop():
        while not stopping.is_set():
            with schedule_lock:
                due = schedule.due(time.monotonic())
                if due:
                    schedule.started(time.monotonic())
            if due:
                app.post_to_main_thread(
                    window, lambda: setattr(status, "text",
                                            "Camera scan running; displaying last cloud..."))
                acquire()
            stopping.wait(0.05)

    def request_once():
        with schedule_lock:
            schedule.request_once()

    def set_auto(checked):
        with schedule_lock:
            schedule.auto = bool(checked)

    scan_once.set_on_clicked(request_once)
    auto.set_on_checked(set_auto)

    def interval_changed(value):
        with schedule_lock:
            schedule.set_interval(value)
        status.text = "Requested camera interval %.3fs" % schedule.interval_s
    interval.set_on_value_changed(interval_changed)
    window.set_on_layout(layout)
    window.set_on_close(lambda: (stopping.set() or True))
    if initial_manifest is not None:
        load_scene(scene_spec(initial_manifest, world_path, crosscheck_path))
    threading.Thread(target=scheduler_loop, name="pixel-pro-scheduler", daemon=True).start()
    app.run()


def benchmark_scans(config: dict, count: int, interval_s: float, output: Path) -> dict:
    """Measure the acquisition scheduler headlessly; camera-only operation."""
    schedule = ScanSchedule(interval_s=interval_s, auto=True)
    records = []
    while len(records) < count:
        now = time.monotonic()
        if schedule.due(now):
            schedule.started(now)
            started = time.monotonic()
            manifest = capture_body_cloud(config)
            elapsed = time.monotonic() - started
            records.append({"manifest": str(manifest.resolve()), "scan_pipeline_s": elapsed})
            schedule.finished()
        else:
            time.sleep(min(0.05, max(0.0, schedule.interval_s - (now - schedule.last_started_monotonic))))
    report = {
        "requested_interval_s": interval_s,
        "actual_start_intervals_s": schedule.actual_start_intervals_s,
        "records": records,
        "render_frequency_decoupled": True,
        "classification": "snapshot-rate viewer; not real-time perception",
    }
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
