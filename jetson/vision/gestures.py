#!/usr/bin/env python3
"""Arm gestures from COCO keypoints (YOLO26-pose) and the robot command they trigger.

Gestures (image y grows downward; keypoint side 0 = person's left, 1 = person's right):
  both_up  both wrists above the nose                         -> STOP (anyone may stop the robot)
  one_up   one wrist above the nose                           -> FOLLOW that person (owner only)
  point    a straight, roughly horizontal arm, not raised     -> GO <direction> (owner only)

A gesture must be held for HOLD seconds and fires once per hold. The GO direction is the
shoulder->wrist vector in 3D (depth-deprojected), as a robot heading: 0 = straight ahead
(away from the camera), negative = robot's left, positive = robot's right.
No robot is attached yet: the command is only shown in the live view and printed.
"""
import math

import numpy as np

KP_CONF = 0.5
HOLD = 0.7           # seconds a gesture must be held
GO_SHOW = 3.0        # seconds a GO command stays active
STRAIGHT_ARM = 150   # minimum elbow angle (deg) for a pointing arm
LEVEL_ARM = 35       # maximum arm tilt from horizontal (deg) for a pointing arm
NOSE, SHOULDER, ELBOW, WRIST = 0, 5, 7, 9  # + side for shoulder / elbow / wrist


def _ok(kp, *idx):
    return all(kp[i, 2] > KP_CONF for i in idx)


def _wrist_up(kp, side):
    s, w = SHOULDER + side, WRIST + side
    if not _ok(kp, s, w):
        return False
    if _ok(kp, NOSE):
        head = kp[NOSE, 1]
    elif _ok(kp, SHOULDER, SHOULDER + 1):  # back turned: one shoulder width above the shoulder
        head = kp[s, 1] - abs(kp[SHOULDER, 0] - kp[SHOULDER + 1, 0])
    else:
        return False
    return kp[w, 1] < head


def _pointing(kp, side):
    s, e, w = SHOULDER + side, ELBOW + side, WRIST + side
    if not _ok(kp, s, e, w):
        return False
    a, b = kp[s, :2] - kp[e, :2], kp[w, :2] - kp[e, :2]
    cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
    elbow = math.degrees(math.acos(np.clip(cos, -1, 1)))
    arm = kp[w, :2] - kp[s, :2]
    tilt = math.degrees(math.atan2(abs(arm[1]), abs(arm[0]) + 1e-9))
    # the arm must also be long in the image (not a short forearm held in front of the body)
    if _ok(kp, SHOULDER, SHOULDER + 1):
        long_enough = np.linalg.norm(arm) > abs(kp[SHOULDER, 0] - kp[SHOULDER + 1, 0])
    else:
        long_enough = True
    return elbow > STRAIGHT_ARM and tilt < LEVEL_ARM and long_enough


def point_heading(kp, side, xyz):
    """Robot heading (deg) of the pointing arm; xyz(u, v) -> camera-frame point in metres or None."""
    s, w = SHOULDER + side, WRIST + side
    ps, pw = xyz(*kp[s, :2]), xyz(*kp[w, :2])
    if ps is None or pw is None:  # no depth at a joint: fall back to image left / right
        return -90.0 if kp[w, 0] < kp[s, 0] else 90.0
    dx, dz = pw[0] - ps[0], pw[2] - ps[2]
    return math.degrees(math.atan2(dx, dz))


def classify(kp, xyz):
    """Return (gesture, heading or None) for one person's keypoints (17 x [x, y, conf]), or None."""
    up = [_wrist_up(kp, 0), _wrist_up(kp, 1)]
    if all(up):
        return "both_up", None
    if any(up):
        return "one_up", None
    for side in (0, 1):
        if _pointing(kp, side):
            return "point", point_heading(kp, side, xyz)
    return None


class Commander:
    """Turns held gestures into a robot command: IDLE, FOLLOW (a track id), STOP, plus a timed GO."""

    def __init__(self):
        self.mode, self.target, self.go = "IDLE", None, None  # go = (heading, until)
        self._held = {}  # track id -> (gesture, since, fired)

    def update(self, now, gestures, owner_tid, owner_required):
        """gestures: {track id: (gesture, heading)}. Returns event strings for the log."""
        events = []
        self._held = {t: h for t, h in self._held.items() if t in gestures}
        for tid, (g, heading) in gestures.items():
            prev = self._held.get(tid)
            if prev is None or prev[0] != g:
                self._held[tid] = (g, now, False)
                continue
            if prev[2] or now - prev[1] < HOLD:
                continue
            self._held[tid] = (g, prev[1], True)
            allowed = not owner_required or tid == owner_tid
            if g == "both_up":
                self.mode, self.target, self.go = "STOP", None, None
                events.append(f"both hands up by #{tid} -> STOP")
            elif g == "one_up" and allowed:
                self.mode, self.target = "FOLLOW", tid
                events.append(f"hand up by #{tid} -> FOLLOW #{tid}")
            elif g == "point" and allowed:
                self.go = (heading, now + GO_SHOW)
                events.append(f"pointing by #{tid} -> GO {heading:+.0f} deg")
            else:
                events.append(f"{g} by #{tid} ignored (not the owner)")
        if self.go is not None and now > self.go[1]:
            self.go = None
        return events
