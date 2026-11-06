"""Runs DeepFace in its own process (so it does not clash with the TF1-style FaceNet graph).
Protocol: reads an image path per line on stdin, answers with a '@@{json}' line on stdout."""
import json
import os
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
try:
    import tf_keras  # noqa: F401  (needed by DeepFace on TF >= 2.16)
    os.environ["TF_USE_LEGACY_KERAS"] = "1"
except ImportError:
    pass

from deepface import DeepFace


def send(obj):
    sys.stdout.write("@@" + json.dumps(obj) + "\n")
    sys.stdout.flush()


send({"ready": True})
for line in sys.stdin:
    path = line.strip()
    if not path:
        continue
    try:
        res = DeepFace.analyze(img_path=path, actions=["emotion"], enforce_detection=False)
        if isinstance(res, list):
            res = res[0]
        send({"dominant": res["dominant_emotion"],
              "scores": {k: float(v) for k, v in res["emotion"].items()}})
    except Exception as e:  # keep the monitor running
        send({"error": str(e)})
