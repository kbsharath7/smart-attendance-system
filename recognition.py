"""Attendance recognition. Usage:
    python recognition.py --out result.json [--allowed 1AB21CS001,1AB21CS002] [--voice]
Press q in the camera window to finish. Writes {"present": [usn, ...]} to --out.
A student is marked once recognised in MIN_HITS frames (avoids one-frame false matches)."""
import argparse
import json
import time

import cv2
import numpy as np
import detect_and_align
import tensorflow.compat.v1 as tf

import face_common as fc
from liveness import LivenessTracker

MIN_HITS = 3
LIVENESS = True      # True = a student must turn the head once (a photo cannot do this)


def open_camera():
    """Open the laptop camera quickly on Windows (DirectShow).
    If that fails for any reason, fall back to the normal way, so it can never be worse."""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)
    return cap


def Play(text1):
    """Optional voice feedback (needs gTTS, pygame, mutagen)."""
    from gtts import gTTS
    from mutagen.mp3 import MP3
    import pygame
    gTTS(text=text1, lang="en", slow=False).save("voice.mp3")
    song = MP3("voice.mp3")
    pygame.mixer.init()
    pygame.mixer.music.load("voice.mp3")
    pygame.mixer.music.play()
    time.sleep(song.info.length)
    pygame.mixer.quit()


def Recognise(out_path=None, allowed=None, voice=False, liveness=LIVENESS):
    Names, hits = [], {}
    tracker = LivenessTracker()
    with tf.Graph().as_default():
        with tf.Session() as sess:
            mtcnn, embeddings, images_ph, phase_ph, id_data = fc.setup(sess)
            cap = open_camera()

            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                face_patches, bbs, landmarks = detect_and_align.detect_faces(frame, mtcnn)
                if len(face_patches) > 0:
                    face_patches = np.stack(face_patches)
                    embs = sess.run(embeddings, feed_dict={images_ph: face_patches, phase_ph: False})
                    matching_ids, matching_distances = id_data.find_matching_ids(embs)

                    for bb, matching_id, dist, lm in zip(bbs, matching_ids, matching_distances, landmarks):
                        if matching_id is None or (allowed and matching_id not in allowed):
                            label, color = "Unknown", (60, 60, 220)
                        else:
                            hits[matching_id] = hits.get(matching_id, 0) + 1
                            live = (not liveness) or tracker.update(matching_id, lm)
                            if hits[matching_id] >= MIN_HITS and live and matching_id not in Names:
                                Names.append(matching_id)
                                print("Marked present: %s (distance %1.4f)" % (matching_id, dist))
                                if voice:
                                    Play("Attendance marked for " + matching_id)
                            if matching_id in Names:
                                label, color = matching_id + " - present", (90, 190, 120)
                            elif hits[matching_id] >= MIN_HITS and not live:
                                label, color = matching_id + " - turn your head", (60, 170, 230)
                            else:
                                label, color = matching_id, (90, 190, 120)
                        cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), color, 2)
                        cv2.putText(frame, label, (bb[0], bb[3] + 22), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, color, 2, cv2.LINE_AA)

                cv2.putText(frame, f"Present: {len(Names)}   [q] finish", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
                if liveness:
                    cv2.putText(frame, "Look at the camera, then slowly turn your head left and right",
                                (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 170, 230), 2, cv2.LINE_AA)
                cv2.imshow("Attendance", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            cap.release()
            cv2.destroyAllWindows()

    if out_path:
        with open(out_path, "w") as f:
            json.dump({"present": Names}, f)
    return Names


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--allowed", default="", help="comma separated USNs of the class")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--no-liveness", action="store_true", help="turn the anti-photo head-turn check off")
    a = ap.parse_args()
    allowed = [x for x in a.allowed.split(",") if x] or None
    print(Recognise(a.out, allowed, a.voice, liveness=not a.no_liveness))
