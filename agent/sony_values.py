"""Turn Sony Camera Remote SDK raw values into words a camera person reads.

Sony sends every setting as a number. Some are simple (f-number x 100),
some are packed (shutter = numerator/denominator in one number), and many
are list choices (white balance = Daylight, Tungsten...). This module
decodes them. List-choice names are read from the developer's own copy of
Sony's header file, so no Sony file lives in this repo.
"""
import re
from pathlib import Path

DEFAULT_HEADER = Path(__file__).resolve().parent.parent / "sdk/RemoteCli/app/CRSDK/CrDeviceProperty.h"

# Setting name -> the Sony list (enum) that names its values.
PROPERTY_ENUMS = {
    "WhiteBalance": "CrWhiteBalanceSetting",
    "FocusMode": "CrFocusMode",
    "FocusArea": "CrFocusArea",
    "FocusIndication": "CrFocusIndicator",
    "NearFar": "CrNearFarEnableStatus",
    "ExposureProgramMode": "CrExposureProgram",
    "ExposureCtrlType": "CrExposureCtrlType",
    "IrisModeSetting": "CrIrisModeSetting",
    "ShutterModeSetting": "CrShutterModeSetting",
    "ShutterMode": "CrShutterMode",
    "ShutterModeStatus": "CrShutterModeStatus",
    "ShutterType": "CrShutterType",
    "GainControlSetting": "CrGainControlSetting",
    "GainBaseIsoSensitivity": "CrGainBaseIsoSensitivity",
    "PictureProfile": "CrPictureProfile",
    "PictureProfile_Gamma": "CrPictureProfileGamma",
    "PictureProfile_ColorMode": "CrPictureProfileColorMode",
    "MovieShootingMode": "CrMovieShootingMode",
    "MovieShootingModeColorGamut": "CrMovieShootingModeColorGamut",
    "LogShootingMode": "CrLogShootingMode",
    "MonitorLUTSetting": "CrMonitorLUTSetting",
    "GammaDisplayAssist": "CrGammaDisplayAssist",
    "CreativeLook": "CrCreativeLook",
    "RecordingState": "CrMovie_Recording_State",
    "Movie_Recording_FrameRateSetting": "CrRecordingFrameRateSettingMovie",
    "Movie_Recording_Setting": "CrRecordingSettingMovie",
    "Movie_File_Format": "CrFileFormatMovie",
    "LiveView_Image_Quality": "CrPropertyLiveViewImageQuality",
    "LiveViewStatus": "CrLiveViewStatus",
    "LiveViewDisplayEffect": "CrLiveViewDisplayEffect",
    "SubjectRecognitionAF": "CrSubjectRecognitionAF",
    "PriorityKeySettings": "CrPriorityKeySettings",
    "BatteryLevel": "CrBatteryLevel",
    "SilentMode": "CrSilentMode",
    "AEL": "CrLockIndicator",
    "AWBL": "CrLockIndicator",
    "FEL": "CrLockIndicator",
}

ISO_AUTO = 0xFFFFFF


def load_enums(header_path=DEFAULT_HEADER):
    """Return {enum type name: {value: short name}} parsed from Sony's header."""
    text = Path(header_path).read_text(encoding="utf-8-sig", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    enums = {}
    for match in re.finditer(r"enum\s+(\w+)\s*:\s*\w+\s*\{(.*?)\}", text, re.S):
        enum_name, body = match.group(1), match.group(2)
        values, known, value = {}, {}, -1
        try:
            for item in body.split(","):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    name, expr = (part.strip() for part in item.split("=", 1))
                    value = known[expr] if expr in known else int(expr, 0)
                else:
                    name, value = item, value + 1
                known[name] = value
                # Drop the common prefix, e.g. CrWhiteBalance_Daylight -> Daylight
                values.setdefault(value, name.split("_", 1)[1] if "_" in name else name)
        except ValueError:
            continue  # enum uses an expression we don't need to understand
        enums[enum_name] = values
    return enums


def fmt_fnumber(v):
    specials = {0xFFFD: "iris closed", 0xFFFE: "--", 0xFFFF: "(none)"}
    if v in specials:
        return specials[v]
    return "f/%g" % (v / 100)


def fmt_shutter(v, half_bits=16):
    """ShutterSpeed packs numerator/denominator in 16+16 bits;
    ExtendedShutterSpeed uses 32+32 bits."""
    mask = (1 << half_bits) - 1
    if v == 0:
        return "Bulb"
    if v == (1 << (2 * half_bits)) - 1:
        return "(none)"
    num, den = v >> half_bits, v & mask
    if den == 0:
        return "raw 0x%X" % v
    if den == 10:
        return '%g"' % (num / 10)
    if num == 1:
        return "1/%d" % den
    return "%d/%d" % (num, den)


def fmt_angle(v):
    return "disabled" if v == 0 else "%g°" % (v / 1000)


def fmt_iso(v):
    iso = v & 0xFFFFFF
    mode = (v >> 24) & 0xF
    text = "ISO AUTO" if iso == ISO_AUTO else "ISO %d" % iso
    if mode:
        text += " (mode %d)" % mode
    return text


def fmt_kelvin(v):
    return {0x0000: "below range", 0xFFFF: "above range"}.get(v, "%dK" % v)


SPECIAL_FORMATS = {
    "FNumber": fmt_fnumber,
    "ShutterSpeed": fmt_shutter,
    "ExtendedShutterSpeed": lambda v: fmt_shutter(v, half_bits=32),
    "ShutterAngle": fmt_angle,
    "IsoSensitivity": fmt_iso,
    "IsoCurrentSensitivity": fmt_iso,
    "Colortemp": fmt_kelvin,
    "ExposureIndex": lambda v: "%d EI" % v,
    "BaseISOSwitchEI": lambda v: "%d EI" % v,
}


def describe_value(prop_name, value, enums):
    """One value -> readable text. Falls back to the raw number."""
    if prop_name in SPECIAL_FORMATS:
        return SPECIAL_FORMATS[prop_name](value)
    enum_name = PROPERTY_ENUMS.get(prop_name)
    if enum_name and enum_name in enums and value in enums[enum_name]:
        return enums[enum_name][value]
    return str(value)


def is_decoded(prop_name, enums):
    if prop_name in SPECIAL_FORMATS:
        return True
    enum_name = PROPERTY_ENUMS.get(prop_name)
    return bool(enum_name and enum_name in enums)


def describe_property(prop, enums):
    """Current value of one property from the probe JSON, as text."""
    if prop["type"] == "STR":
        return prop.get("current_str", "")
    return describe_value(prop["name"], prop["current"], enums)


def describe_choices(prop, enums, limit=10):
    """Allowed values, short form. Ranges show min..max step."""
    if prop["type"] == "STR":
        return ""
    values = prop["set_values"] or prop["values"]
    if not values:
        return ""
    if prop["type"].endswith("Range") and len(values) == 3:
        lo, hi, step = values
        return "%s .. %s (step %s)" % (describe_value(prop["name"], lo, enums),
                                       describe_value(prop["name"], hi, enums), step)
    names = [describe_value(prop["name"], v, enums) for v in values]
    if len(names) <= limit:
        return ", ".join(names)
    return "%d options: %s ... %s" % (len(names), ", ".join(names[:4]), ", ".join(names[-3:]))
