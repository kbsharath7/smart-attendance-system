"""Shared FaceNet + MTCNN helpers used by dataset.py, recognition.py and monitor.py
(this is the IdData / load_model code from your original scripts, with a few guards)."""
import os

from sklearn.metrics.pairwise import pairwise_distances
from tensorflow.python.platform import gfile
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()
import numpy as np
import cv2
import detect_and_align

MODEL_PATH = "20170512-110547/20170512-110547.pb"
ID_FOLDER = "20170512-110547/ids"


class IdData:
    """Keeps track of known identities and calculates id matches"""

    def __init__(self, id_folder, mtcnn, sess, embeddings, images_placeholder,
                 phase_train_placeholder, distance_treshold):
        print("Loading known identities: ", end="")
        self.distance_treshold = distance_treshold
        self.id_folder = id_folder
        self.mtcnn = mtcnn
        self.id_names = []
        self.embeddings = None

        os.makedirs(id_folder, exist_ok=True)
        image_paths = []
        for id_name in os.listdir(os.path.expanduser(id_folder)):
            id_dir = os.path.join(id_folder, id_name)
            if os.path.isdir(id_dir):
                image_paths += [os.path.join(id_dir, img) for img in os.listdir(id_dir)]
        if not image_paths:
            print("no images yet")
            return

        print("Found %d images in id folder" % len(image_paths))
        aligned_images, id_image_paths = self.detect_id_faces(image_paths)
        if aligned_images is None:
            return
        feed_dict = {images_placeholder: aligned_images, phase_train_placeholder: False}
        self.embeddings = sess.run(embeddings, feed_dict=feed_dict)

    def add_id(self, embedding, new_id, face_patch):
        if self.embeddings is None:
            self.embeddings = np.atleast_2d(embedding)
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])
        self.id_names.append(new_id)
        id_folder = os.path.join(self.id_folder, new_id)
        os.makedirs(id_folder, exist_ok=True)
        filenames = [s.split(".")[0] for s in os.listdir(id_folder)]
        numbered = [int(f) for f in filenames if f.isdigit()]
        img_number = max(numbered) + 1 if numbered else 0
        cv2.imwrite(os.path.join(id_folder, f"{img_number}.jpg"), face_patch)

    def detect_id_faces(self, image_paths):
        aligned_images, id_image_paths = [], []
        for image_path in image_paths:
            image = cv2.imread(os.path.expanduser(image_path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_patches, _, _ = detect_and_align.detect_faces(image, self.mtcnn)
            if len(face_patches) > 1:
                print("Warning: multiple faces found in id image: %s" % image_path)
            aligned_images = aligned_images + face_patches
            id_image_paths += [image_path] * len(face_patches)
            self.id_names += [os.path.basename(os.path.dirname(image_path))] * len(face_patches)
        if not aligned_images:
            return None, []
        return np.stack(aligned_images), id_image_paths

    def find_matching_ids(self, embs):
        if self.id_names and self.embeddings is not None:
            matching_ids, matching_distances = [], []
            distance_matrix = pairwise_distances(embs, self.embeddings)
            for distance_row in distance_matrix:
                min_index = np.argmin(distance_row)
                if distance_row[min_index] < self.distance_treshold:
                    matching_ids.append(self.id_names[min_index])
                    matching_distances.append(distance_row[min_index])
                else:
                    matching_ids.append(None)
                    matching_distances.append(None)
        else:
            matching_ids = [None] * len(embs)
            matching_distances = [np.inf] * len(embs)
        return matching_ids, matching_distances


def load_model(model):
    model_exp = os.path.expanduser(model)
    if os.path.isfile(model_exp):
        print("Loading model filename: %s" % model_exp)
        with gfile.FastGFile(model_exp, "rb") as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            tf.import_graph_def(graph_def, name="")
    else:
        raise ValueError("Specify model file, not directory!")


def setup(sess, threshold=1.0):
    """Create MTCNN, load FaceNet and the known identities."""
    mtcnn = detect_and_align.create_mtcnn(sess, None)
    load_model(MODEL_PATH)
    graph = tf.get_default_graph()
    images_placeholder = graph.get_tensor_by_name("input:0")
    embeddings = graph.get_tensor_by_name("embeddings:0")
    phase_train_placeholder = graph.get_tensor_by_name("phase_train:0")
    id_data = IdData(ID_FOLDER, mtcnn, sess, embeddings, images_placeholder,
                     phase_train_placeholder, threshold)
    return mtcnn, embeddings, images_placeholder, phase_train_placeholder, id_data


def crop(frame, bb):
    return frame[max(bb[1], 0):bb[3], max(bb[0], 0):bb[2], :]
