"""'This face looks right' (agent/faces.py), with a stand-in for the SFace model."""
import json

import numpy as np

from agent.faces import FaceBook

SIGNATURES = {"ana": [1, 0, 0, 0], "ben": [0, 1, 0, 0]}


def face(who, x=100, stops=-1.0):
    return {"box": [x, 50, 80, 80], "stops": stops, "raw": [x], "who": who}


def book(tmp_path):
    signer = lambda bgr, f: np.array(SIGNATURES[f["who"]], np.float32) + np.random.default_rng(1).normal(0, 0.05, 4)
    return FaceBook(tmp_path / "refs.json", signer=signer)


def test_remembered_person_is_recognized_and_keeps_their_target(tmp_path):
    b = book(tmp_path)
    b.remember("Ana", None, face("ana"), -0.4)
    faces = b.label(None, [face("ana", x=300), face("ben", x=600)], t=10.0)
    assert faces[0]["name"] == "Ana" and faces[0]["target"] == -0.4
    assert "name" not in faces[1]                                   # Ben was never set: look default


def test_setting_the_same_person_again_updates_instead_of_duplicating(tmp_path):
    b = book(tmp_path)
    b.remember("Ana", None, face("ana"), -0.4)
    b.remember(None, None, face("ana"), 0.2)
    assert [(p["name"], p["target"]) for p in b.people] == [("Ana", 0.2)]


def test_forget_and_summary_never_expose_signatures(tmp_path):
    b = book(tmp_path)
    ana = b.remember("Ana", None, face("ana"), -0.4)
    b.remember("Ben", None, face("ben"), 0.5)
    assert all("signature" not in p for p in b.summary())
    b.forget(ana["id"])
    saved = json.loads((tmp_path / "refs.json").read_text())["people"]
    assert [p["name"] for p in saved] == ["Ben"]
    assert "name" not in b.label(None, [face("ana")], t=0.0)[0]
