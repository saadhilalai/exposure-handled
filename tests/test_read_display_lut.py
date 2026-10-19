"""Reading the Display LUT (tools/read_display_lut.py), with made-up camera answers."""
from agent.sony_values import load_enums
from tools.read_display_lut import decode_base_look, summarize


def test_base_look_codes_follow_sonys_layout():
    assert decode_base_look(0x0003) == ("Preset", 3)
    assert decode_base_look(0x0108) == ("User", 8)
    assert decode_base_look(0x8201) == ("Temporary copy of Scene file", 1)


def test_summary_names_the_selected_look():
    props = {"BaseLookValue": {"current": 0x0101}, "MonitorLUTSetting": {"current": 2}}
    names = [{"value": 0x0001, "text": "Look one"}, {"value": 0x0101, "text": "My user LUT"}]
    s = summarize(props, names, [], [], load_enums())
    assert s["name"] == "My user LUT" and s["kind"] == "User" and "My user LUT" in s["answer"]


def test_summary_without_names_still_gives_kind_and_index():
    s = summarize({"BaseLookValue": {"current": 0x0002}}, [], [], [], load_enums())
    assert "Preset #2 (name not reported)" in s["answer"]
