// Shared helpers for talking to Sony's Camera Remote SDK: names, JSON, value decoding.
// Nothing in this file can change camera settings.
#pragma once

#include <chrono>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "CameraRemote_SDK.h"
#include "CrDeviceProperty.h"

namespace sdkutil {

namespace SDK = SCRSDK;

inline const std::map<CrInt32u, const char*>& property_names() {
    static const std::map<CrInt32u, const char*> names = {
#include "property_names.inc"
    };
    return names;
}

inline std::string property_name(CrInt32u code) {
    auto it = property_names().find(code);
    if (it != property_names().end()) return it->second;
    std::ostringstream s;
    s << "Unknown_0x" << std::hex << std::uppercase << code;
    return s.str();
}

// Name -> code. Returns false if the name is unknown.
inline bool property_code(const std::string& name, CrInt32u* code) {
    for (const auto& [c, n] : property_names()) {
        if (name == n) {
            *code = c;
            return true;
        }
    }
    return false;
}

inline std::string now_iso() {
    using namespace std::chrono;
    auto now = system_clock::now();
    std::time_t t = system_clock::to_time_t(now);
    int ms = int(duration_cast<milliseconds>(now.time_since_epoch()).count() % 1000);
    char buf[40];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", std::localtime(&t));
    std::ostringstream s;
    s << buf << "." << std::setw(3) << std::setfill('0') << ms;
    return s.str();
}

// Monotonic clock in nanoseconds, for measuring how long things take.
inline long long steady_ns() {
    using namespace std::chrono;
    return duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count();
}

inline std::string json_escape(const std::string& in) {
    std::ostringstream out;
    for (unsigned char c : in) {
        switch (c) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
                else out << c;
        }
    }
    return out.str();
}

// Sony strings are UTF-16: first element is the length, then the characters.
inline std::string sony_str_to_utf8(const CrInt16u* str) {
    if (!str || str[0] == 0) return "";
    std::string out;
    for (CrInt16u i = 1; i <= str[0]; ++i) {
        CrInt16u ch = str[i];
        if (ch == 0) break;
        if (ch < 0x80) {
            out += char(ch);
        } else if (ch < 0x800) {
            out += char(0xC0 | (ch >> 6));
            out += char(0x80 | (ch & 0x3F));
        } else {
            out += char(0xE0 | (ch >> 12));
            out += char(0x80 | ((ch >> 6) & 0x3F));
            out += char(0x80 | (ch & 0x3F));
        }
    }
    return out;
}

inline std::string type_name(CrInt32u type) {
    if (type == SDK::CrDataType_STR) return "STR";
    if (type == SDK::CrDataType_Undefined) return "Undefined";
    std::string base;
    switch (type & 0x000F) {
        case 1: base = "8"; break;
        case 2: base = "16"; break;
        case 3: base = "32"; break;
        case 4: base = "64"; break;
        case 5: base = "128"; break;
        default: base = "?"; break;
    }
    std::string name = ((type & SDK::CrDataType_SignBit) ? "Int" : "UInt") + base;
    if (type & SDK::CrDataType_CustomBit) name = "Custom" + name;
    if (type & SDK::CrDataType_ArrayBit) name += "Array";
    if (type & SDK::CrDataType_RangeBit) name += "Range";
    return name;
}

inline const char* enable_flag_name(int flag) {
    switch (flag) {
        case SDK::CrEnableValue_NotSupported: return "NotSupported";
        case SDK::CrEnableValue_False: return "False";
        case SDK::CrEnableValue_True: return "True";
        case SDK::CrEnableValue_DisplayOnly: return "DisplayOnly";
        case SDK::CrEnableValue_SetOnly: return "SetOnly";
        default: return "Other";
    }
}

// Decode a packed list of candidate values (array) or min/max/step (range).
inline std::vector<long long> decode_values(CrInt32u type, const CrInt8u* data, CrInt32u size) {
    std::vector<long long> out;
    if (!data || size == 0 || type == SDK::CrDataType_STR) return out;
    CrInt32u elem = 0;
    switch (type & 0x000F) {
        case 1: elem = 1; break;
        case 2: elem = 2; break;
        case 3: elem = 4; break;
        case 4: elem = 8; break;
        default: return out;  // 128-bit values are not used by the settings we need
    }
    bool is_signed = (type & SDK::CrDataType_SignBit) != 0;
    for (CrInt32u off = 0; off + elem <= size; off += elem) {
        long long v = 0;
        switch (elem) {
            case 1: { CrInt8u x; std::memcpy(&x, data + off, 1); v = is_signed ? (long long)(int8_t)x : x; break; }
            case 2: { CrInt16u x; std::memcpy(&x, data + off, 2); v = is_signed ? (long long)(int16_t)x : x; break; }
            case 4: { CrInt32u x; std::memcpy(&x, data + off, 4); v = is_signed ? (long long)(int32_t)x : x; break; }
            case 8: { CrInt64u x; std::memcpy(&x, data + off, 8); v = (long long)x; break; }
        }
        out.push_back(v);
    }
    return out;
}

// Values the camera will accept right now: the "set" list if present, else the general list.
inline std::vector<long long> settable_values(const SDK::CrDeviceProperty& p) {
    auto values = decode_values(p.GetValueType(), p.GetSetValues(), p.GetSetValueSize());
    if (values.empty()) values = decode_values(p.GetValueType(), p.GetValues(), p.GetValueSize());
    return values;
}

inline std::string list_json(const std::vector<long long>& values) {
    std::ostringstream out;
    out << "[";
    for (size_t i = 0; i < values.size(); ++i) out << (i ? ", " : "") << values[i];
    out << "]";
    return out.str();
}

// One property as a JSON object (same shape the probe has always written).
inline std::string property_json(const SDK::CrDeviceProperty& p) {
    CrInt32u type = p.GetValueType();
    std::ostringstream out;
    out << "{\"code\": " << p.GetCode()
        << ", \"name\": \"" << json_escape(property_name(p.GetCode())) << "\""
        << ", \"type\": \"" << type_name(type) << "\""
        << ", \"enable\": \"" << enable_flag_name(p.GetPropertyEnableFlag()) << "\""
        << ", \"can_read\": " << (p.IsGetEnableCurrentValue() ? "true" : "false")
        << ", \"can_set_now\": " << (p.IsSetEnableCurrentValue() ? "true" : "false")
        << ", \"current\": " << p.GetCurrentValue();
    if (type == SDK::CrDataType_STR)
        out << ", \"current_str\": \"" << json_escape(sony_str_to_utf8(p.GetCurrentStr())) << "\"";
    out << ", \"values\": " << list_json(decode_values(type, p.GetValues(), p.GetValueSize()))
        << ", \"set_values\": " << list_json(decode_values(type, p.GetSetValues(), p.GetSetValueSize()))
        << "}";
    return out.str();
}

}  // namespace sdkutil
