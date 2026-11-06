"""Face enrolment. Usage:  python dataset.py <USN>
Camera window controls:  c = capture a sample   q = finish
The Flask admin page calls this script with the student's USN, so every
folder in  20170512-110547/ids/  is named after a USN."""
import sys

import cv2
import numpy as np
import detect_and_align
import tensorflow.compat.v1 as tf

import face_common as fc

SAMPLES = 5


def open_camera():
    """Open the laptop camera quickly on Windows (DirectShow).
    If that fails for any reason, fall back to the normal way, so it can never be worse."""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)
    return cap


def create_dataset(name, samples=SAMPLES):
    captured = 0
    with tf.Graph().as_default():
        with tf.Session() as sess:
            mtcnn, embeddings, images_ph, phase_ph, id_data = fc.setup(sess)

            cap = open_camera()
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Camera not available")
                    break

                face_patches, bbs, _ = detect_and_align.detect_faces(frame, mtcnn)
                display = frame.copy()
                for bb in bbs:
                    cv2.rectangle(display, (bb[0], bb[1]), (bb[2], bb[3]), (80, 200, 120), 2)
                cv2.putText(display, f"{name}  samples {captured}/{samples}   [c] capture  [q] finish",
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("Register face", display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("c"):
                    if len(face_patches) == 0:
                        print("No face found - try again")
                        continue
                    # use the biggest face in the frame
                    idx = int(np.argmax([(b[2] - b[0]) * (b[3] - b[1]) for b in bbs]))
                    emb = sess.run(embeddings, feed_dict={
                        images_ph: np.stack([face_patches[idx]]), phase_ph: False})[0]
                    id_data.add_id(emb, name, fc.crop(frame, bbs[idx]))
                    captured += 1
                    print(f"Captured {captured}/{samples}")
                    if captured >= samples:
                        break
                elif key == ord("q"):
                    break
            cap.release()
            cv2.destroyAllWindows()
    return captured


if __name__ == "__main__":
    student = sys.argv[1] if len(sys.argv) > 1 else input("Enter the student USN: ").strip()
    n = create_dataset(student)
    sys.exit(0 if n > 0 else 1)
