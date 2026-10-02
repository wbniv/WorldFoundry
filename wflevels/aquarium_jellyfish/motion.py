"""Chosen game approximations informed by the primary studies in the poster plan.

These constants are not fitted biological data or a fluid simulation.
"""
CONTRACT_FRACTION=.20
RECOVER_FRACTION=.30
COAST_FRACTION=.50
PLAYER_PERIOD=4.0
RESIDENT_PERIODS=(4.0,4.35,4.70,5.05,5.40)
RADIAL_CONTRACTION=.18
HEIGHT_INCREASE=.28
ARM_LAG=.10  # cycle fraction, an illustrative game choice
ARM_TILT_A=.022  # turns
ARM_TILT_B=.010
RESIDENT_POSE_INTERVAL=1/30


def contraction(phase):
    p=phase%1
    if p<CONTRACT_FRACTION:
        u=p/CONTRACT_FRACTION
    elif p<CONTRACT_FRACTION+RECOVER_FRACTION:
        u=(p-CONTRACT_FRACTION)/RECOVER_FRACTION
        return 1-u*u*(3-2*u)
    else:return 0
    return u*u*(3-2*u)
