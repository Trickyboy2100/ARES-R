"""Deterministic BODY projection semantics used by UI regression tests."""

import math


def rear_screen_x(point_body, pixels_per_m=1.0):
    """Robot-forward/rear view: BODY +Y (left) is screen-left."""
    return -float(point_body[1])*float(pixels_per_m)


def assert_body_handedness():
    left=rear_screen_x((0,.20,1.2));right=rear_screen_x((0,-.20,1.2))
    return {"left_base_screen_x":left,"right_base_screen_x":right,
            "left_is_screen_left":left<right,
            "body_axes":"+X FORWARD, +Y LEFT, +Z UP"}
