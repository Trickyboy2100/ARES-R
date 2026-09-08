"""Separate bounds for fixed-start repositioning and the 20 cm demonstration.

Repositioning remains bounded and right-only; these do not replace site limits.
"""
# Site-commissioned single-turn reposition bound. 150 deg covers the measured
# hand-posed -> ready case (J4 136.3 deg) while still rejecting wrap-like moves.
RESET_MAX_EXCURSION_DEG = 150.0
RESET_MAX_TCP_LENGTH_M = 1.5
RESET_MAX_DURATION_S = 240.0
