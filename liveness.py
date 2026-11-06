"""Anti-photo check ("liveness") for the attendance camera.

Idea: a real face is 3D - the nose sticks out - so when the head turns, the nose moves
sideways *relative to the two eyes*. A flat photo (even if it is tilted, rotated or moved
about) keeps almost the same nose-to-eyes ratio, so it never shows this change.

It uses the 5 landmarks that MTCNN already returns (left eye, right eye, nose, mouth
left, mouth right), so no new library or model is needed.
"""
import time
from collections import defaultdict, deque

SPREAD_NEEDED = 0.18   # how much the nose offset must change (turning the head left and right gives about 0.3-0.5)
WINDOW_SECONDS = 8     # the turn must happen inside this time
MIN_SAMPLES = 8        # frames needed before a decision is made


def nose_offset(landmark):
    """Nose position along the eye line, relative to the eye centre, divided by the eye distance.
    About 0 when the face looks straight at the camera, + or - when the head turns.
    It is measured along the line between the eyes, so tilting or spinning the picture
    (roll) does not change it."""
    lx, rx, nx = float(landmark[0]), float(landmark[1]), float(landmark[2])
    ly, ry, ny = float(landmark[5]), float(landmark[6]), float(landmark[7])
    ex, ey = rx - lx, ry - ly                      # eye-to-eye vector
    eye_len2 = ex * ex + ey * ey
    if eye_len2 < 64:                              # eyes less than 8 px apart: bad detection
        return None
    mx, my = (lx + rx) / 2.0, (ly + ry) / 2.0      # centre between the eyes
    return ((nx - mx) * ex + (ny - my) * ey) / eye_len2


def _median3(values):
    """Running median of 3 - removes a single wrong frame (a glitch)."""
    if len(values) < 3:
        return list(values)
    return [sorted(values[i:i + 3])[1] for i in range(len(values) - 2)]


class LivenessTracker:
    def __init__(self, spread_needed=SPREAD_NEEDED, window=WINDOW_SECONDS, min_samples=MIN_SAMPLES):
        self.spread_needed = spread_needed
        self.window = window
        self.min_samples = min_samples
        self.history = defaultdict(deque)    # person id -> deque of (time, offset)
        self.live = set()

    def update(self, who, landmark, now=None):
        """Feed one frame for a recognised person. Returns True once they have shown a real head turn."""
        if who in self.live:
            return True
        now = time.time() if now is None else now
        r = nose_offset(landmark)
        if r is None:
            return False
        h = self.history[who]
        h.append((now, r))
        while h and now - h[0][0] > self.window:
            h.popleft()
        if len(h) >= self.min_samples:
            smooth = _median3([v for _, v in h])
            if smooth and max(smooth) - min(smooth) >= self.spread_needed:
                self.live.add(who)
                return True
        return False
