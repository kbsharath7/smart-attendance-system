"""Class monitoring: FaceNet identifies each student, DeepFace reads the emotion.
Usage: python monitor.py --out result.json [--allowed USN1,USN2] [--duration 0]
Press q to finish. Writes {usn: {happy: n, ..., samples: n}} to --out."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import cv2
import numpy as np
import detect_and_align
import tensorflow.compat.v1 as tf

import face_common as fc

EMOTIONS = ["happy", "surprise", "neutral", "sad", "fear", "angry", "disgust"]
COLORS = {"happy": (90, 190, 120), "surprise": (200, 140, 60), "neutral": (170, 170, 170),
          "sad": (180, 100, 110), "fear": (60, 170, 230), "angry": (60, 60, 220), "disgust": (60, 120, 140)}
ANALYSE_EVERY = 1.0  # seconds between emotion samples


def open_camera():
    """Open the laptop camera quickly on Windows (DirectShow).
    If that fails for any reason, fall back to the normal way, so it can never be worse."""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)
    return cap


class EmotionClient:
    def __init__(self):
        here = os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(here, "emotion_worker.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._read()  # wait for ready

    def _read(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("emotion worker stopped - is DeepFace installed?")
            if line.startswith("@@"):
                return json.loads(line[2:])

    def analyse(self, image):
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            cv2.imwrite(path, image)
            self.proc.stdin.write(path + "\n")
            self.proc.stdin.flush()
            return self._read()
        finally:
            os.remove(path)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


def monitor(out_path, allowed=None, duration=0):
    stats = {}
    last_emotion = {}
    emo = EmotionClient()
    last_run = 0
    started = time.time()
    with tf.Graph().as_default():
        with tf.Session() as sess:
            mtcnn, embeddings, images_ph, phase_ph, id_data = fc.setup(sess)
            cap = open_camera()
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                raw = frame.copy()
                face_patches, bbs, _ = detect_and_align.detect_faces(frame, mtcnn)
                run_emotion = time.time() - last_run >= ANALYSE_EVERY

                if len(face_patches) > 0:
                    embs = sess.run(embeddings, feed_dict={
                        images_ph: np.stack(face_patches), phase_ph: False})
                    ids, _ = id_data.find_matching_ids(embs)
                    for bb, usn in zip(bbs, ids):
                        if usn is None or (allowed and usn not in allowed):
                            cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), (60, 60, 220), 1)
                            continue
                        if run_emotion:
                            patch = fc.crop(raw, bb)
                            if patch.size:
                                r = emo.analyse(patch)
                                dom = r.get("dominant")
                                if dom in EMOTIONS:
                                    s = stats.setdefault(usn, {e: 0 for e in EMOTIONS})
                                    s[dom] += 1
                                    last_emotion[usn] = dom
                        e = last_emotion.get(usn, "...")
                        col = COLORS.get(e, (255, 255, 255))
                        cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), col, 2)
                        cv2.putText(frame, f"{usn} {e}", (bb[0], bb[3] + 22),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2, cv2.LINE_AA)
                    if run_emotion:
                        last_run = time.time()

                elapsed = int(time.time() - started)
                cv2.putText(frame, f"Monitoring {elapsed}s  students seen: {len(stats)}   [q] finish",
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("Class monitoring", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                if duration and elapsed >= duration:
                    break
            cap.release()
            cv2.destroyAllWindows()
    emo.close()

    for s in stats.values():
        s["samples"] = sum(s[e] for e in EMOTIONS)
    with open(out_path, "w") as f:
        json.dump(stats, f)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--allowed", default="")
    ap.add_argument("--duration", type=int, default=0, help="auto stop after N seconds (0 = manual)")
    a = ap.parse_args()
    monitor(a.out, [x for x in a.allowed.split(",") if x] or None, a.duration)
