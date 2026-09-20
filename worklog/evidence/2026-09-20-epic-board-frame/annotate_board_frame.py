#!/usr/bin/env python3
"""Project the Epic SDK board pose onto its returned 2D image."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
AXIS_LENGTH_MM = 140.0  # Four 35 mm board grid intervals.


def quaternion_xyzw_to_matrix(q: np.ndarray) -> np.ndarray:
    q = q.astype(np.float64)
    q /= np.linalg.norm(q)
    x, y, z, w = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def outlined_text(image, text, point, color, scale=0.85, thickness=2):
    cv2.putText(image, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
    cv2.putText(image, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def arrow(image, start, end, color, label, label_offset=(8, -8)):
    cv2.arrowedLine(image, start, end, (0, 0, 0), 13, cv2.LINE_AA, tipLength=0.14)
    cv2.arrowedLine(image, start, end, color, 7, cv2.LINE_AA, tipLength=0.14)
    label_point = (end[0] + label_offset[0], end[1] + label_offset[1])
    outlined_text(image, label, label_point, color, 0.88, 2)


with (ROOT / "board_pose.json").open(encoding="utf-8") as handle:
    pose = json.load(handle)
with (ROOT / "camera_parameters.json").open(encoding="utf-8") as handle:
    camera = json.load(handle)

image = cv2.imread(str(ROOT / "sdk_board_pose_raw.png"), cv2.IMREAD_COLOR)
if image is None:
    raise RuntimeError("Could not read sdk_board_pose_raw.png")

translation = pose["board"]["translation"]
rotation = pose["board"]["rotation"]
tvec = np.array([translation["x"], translation["y"], translation["z"]], dtype=np.float64)
q = np.array([rotation["x"], rotation["y"], rotation["z"], rotation["w"]], dtype=np.float64)
R = quaternion_xyzw_to_matrix(q)
rvec, _ = cv2.Rodrigues(R)
K = np.array(camera["CameraIntri"], dtype=np.float64).reshape(3, 3)
dist = np.array(camera["CameraDist"], dtype=np.float64)

board_points = np.array(
    [
        [0.0, 0.0, 0.0],
        [AXIS_LENGTH_MM, 0.0, 0.0],
        [0.0, AXIS_LENGTH_MM, 0.0],
        [0.0, 0.0, AXIS_LENGTH_MM],
    ],
    dtype=np.float64,
)
pixels, _ = cv2.projectPoints(board_points, rvec, tvec, K, dist)
pixels = np.rint(pixels.reshape(-1, 2)).astype(int)
origin, x_end, y_end, z_end = [tuple(p) for p in pixels]

# Standard robotics colors: X red, Y green, Z blue.
arrow(image, origin, x_end, (0, 0, 255), "+X  short edge", (8, 25))
arrow(image, origin, y_end, (0, 210, 0), "+Y  long edge", (8, -10))
arrow(image, origin, z_end, (255, 80, 0), "+Z  normal toward camera", (-20, -14))
cv2.circle(image, origin, 15, (0, 0, 0), -1, cv2.LINE_AA)
cv2.circle(image, origin, 10, (255, 255, 255), -1, cv2.LINE_AA)
cv2.circle(image, origin, 5, (0, 220, 255), -1, cv2.LINE_AA)
outlined_text(image, "O  SDK board origin", (origin[0] + 22, origin[1] - 20), (255, 255, 255), 0.85, 2)
outlined_text(image, "right-angle marker diagonally opposite the label", (origin[0] + 22, origin[1] + 13), (255, 255, 255), 0.65, 2)

# Mark the printed board label to make "diagonally opposite" visually unambiguous.
label_anchor = (535, 510)
cv2.circle(image, label_anchor, 9, (0, 0, 0), -1, cv2.LINE_AA)
cv2.circle(image, label_anchor, 5, (0, 220, 255), -1, cv2.LINE_AA)
cv2.line(image, label_anchor, (780, 650), (0, 0, 0), 7, cv2.LINE_AA)
cv2.line(image, label_anchor, (780, 650), (0, 220, 255), 3, cv2.LINE_AA)
outlined_text(image, "Printed board label", (790, 658), (0, 220, 255), 0.8, 2)

# Add a compact evidence panel without covering the board.
overlay = image.copy()
cv2.rectangle(overlay, (1050, 32), (1880, 260), (15, 15, 15), -1)
cv2.addWeighted(overlay, 0.78, image, 0.22, 0, image)
lines = [
    "Epic HEC-Board-35 / Pixel Pro SDK 4.0.0",
    "Origin: right-angle marker diagonal from label",
    "X: short edge   Y: long edge   Z: surface normal",
    "Pose frame: CAMERA; translation unit: mm",
    f"t = [{tvec[0]:.1f}, {tvec[1]:.1f}, {tvec[2]:.1f}] mm",
    f"Projected O = ({origin[0]}, {origin[1]}) px",
]
for index, line in enumerate(lines):
    outlined_text(image, line, (1080, 70 + index * 34), (245, 245, 245), 0.67, 1)

cv2.imwrite(str(ROOT / "board_pose_axes_annotated.png"), image)

# Board-focused version for easier inspection while preserving the full image above.
x0, y0, x1, y1 = 55, 150, 930, 700
zoom = image[y0:y1, x0:x1]
zoom = cv2.resize(zoom, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
cv2.imwrite(str(ROOT / "board_pose_axes_zoom.png"), zoom)

print(
    json.dumps(
        {
            "axis_length_mm": AXIS_LENGTH_MM,
            "origin_px": [int(value) for value in origin],
            "x_endpoint_px": [int(value) for value in x_end],
            "y_endpoint_px": [int(value) for value in y_end],
            "z_endpoint_px": [int(value) for value in z_end],
        },
        indent=2,
    )
)
