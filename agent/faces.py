"""'This face looks right': set each person's face exposure once.

The director frames someone and presses the button. The agent stores two things:
a face signature (128 numbers from OpenCV's SFace model, so it can recognize the
person later) and how bright that face measured (stops vs 18% grey). From then on,
whenever the eyes find that person, the brain holds their face at that exposure
instead of the look's default (+0.5).

There is no skin-tone classification anywhere: the cinematographer's eye sets the
target, person by person. Signatures are biometric data, so they are stored only on
this computer (config/face_refs.json, never committed), and "forget" deletes them.
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FACE_REFS_FILE = ROOT / "config" / "face_refs.json"
SFACE_MODEL = ROOT / "models" / "face_recognition_sface_2021dec.onnx"
SAME_PERSON = 0.363      # cosine similarity; the threshold OpenCV's own SFace sample uses
REUSE_S = 1.0            # a face that hasn't moved keeps its identity this long before re-checking


def overlap(a, b):
    """Intersection over union of two [x, y, w, h] boxes."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / float(a[2] * a[3] + b[2] * b[3] - inter or 1)


class FaceBook:
    def __init__(self, path=FACE_REFS_FILE, model=SFACE_MODEL, signer=None):
        """signer(bgr, face) -> signature vector. Default: SFace (None if the model isn't downloaded)."""
        self.path = Path(path)
        self.people = json.loads(self.path.read_text())["people"] if self.path.exists() else []
        self.model = Path(model)
        self._signer = signer
        self.recent = []                     # [(box, person or None, score, t)] from the last frames
        self.mutex = threading.RLock()       # the dashboard button and the agent loop share the model

    @property
    def available(self):
        return self._signer is not None or self.model.exists()

    def signer(self, bgr, face):
        with self.mutex:
            if self._signer is None:         # load SFace (39 MB) only when it's first needed
                recognizer = cv2.FaceRecognizerSF.create(str(self.model), "")
                self._signer = lambda img, f: recognizer.feature(
                    recognizer.alignCrop(img, np.array(f["raw"], np.float32))).flatten()
            return self._signer(bgr, face)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"note": "Face signatures + approved face exposure. Local only; "
                                                  "never commit.", "people": self.people}, indent=1))

    def _match(self, signature):
        best, best_score = None, -1.0
        sig = signature / (np.linalg.norm(signature) or 1.0)
        for person in self.people:
            ref = np.array(person["signature"], np.float32)
            score = float(sig @ (ref / (np.linalg.norm(ref) or 1.0)))
            if score > best_score:
                best, best_score = person, score
        return (best, best_score) if best_score >= SAME_PERSON else (None, best_score)

    def label(self, bgr, faces, t):
        """Add "name" and "target" to each face that belongs to a known person. Cheap: a face that
        stays put keeps its identity for REUSE_S before its signature is checked again."""
        with self.mutex:
            return self._label(bgr, faces, t)

    def _label(self, bgr, faces, t):
        if not self.available or not self.people:
            return faces
        recent = []
        for face in faces:
            if "raw" not in face:
                continue
            prev = next((r for r in self.recent if overlap(r[0], face["box"]) > 0.3 and t - r[3] < REUSE_S), None)
            if prev:
                person, score, seen = prev[1], prev[2], prev[3]
            else:
                person, score = self._match(self.signer(bgr, face))
                seen = t
            recent.append((face["box"], person, score, seen))
            if person:
                face["name"], face["target"], face["match"] = person["name"], person["target"], round(score, 2)
        self.recent = recent
        return faces

    def remember(self, name, bgr, face, stops):
        """'This face looks right': store (or update) this person with `stops` as their face exposure."""
        if not self.available:
            raise RuntimeError("face signatures need models/face_recognition_sface_2021dec.onnx "
                               "(run tools/fetch_models.sh)")
        with self.mutex:
            return self._remember(name, bgr, face, stops)

    def _remember(self, name, bgr, face, stops):
        signature = self.signer(bgr, face)
        person, _ = self._match(signature)
        if person is None:
            person = {"id": uuid.uuid4().hex[:8], "name": name or "Person %d" % (len(self.people) + 1)}
            self.people.append(person)
        elif name:
            person["name"] = name
        person.update(target=round(float(stops), 2), signature=[round(float(v), 5) for v in signature],
                      set_at=datetime.now().isoformat(timespec="seconds"))
        self.recent = []
        self._save()
        return person

    def forget(self, person_id):
        with self.mutex:
            self.people = [p for p in self.people if p["id"] != person_id]
            self.recent = []
            self._save()

    def summary(self):
        """People without their signatures (safe to show on the dashboard)."""
        return [{k: p[k] for k in ("id", "name", "target", "set_at")} for p in self.people]
