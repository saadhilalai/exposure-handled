// camera_bridge: holds the connection to the camera and serves a private local socket
// that the Python agent talks to.
//
// Protocol: one text command per line; every answer is one JSON line.
//   ping
//   status
//   settings                        every setting the camera reports
//   get <Name> [<Name> ...]         selected settings, by Sony name (e.g. IsoSensitivity)
//   frame <after_frame_no> <ms>     waits for a live-view frame newer than <after_frame_no>
//                                   (-1 = any). Answer: JSON line with "bytes": N, then N JPEG bytes.
//   lvstats [reset]                 live-view counters measured inside the bridge
//   display_strings <type_id>       the camera's own menu text for a list (e.g. 8 = base ISO)
//   set <Name> <raw_value>          the ONLY way to change the camera (see guarded_set)
//   lock                            kill switch: refuse every change until the bridge restarts
//   quit                            disconnect from the camera and exit
//
// Safety:
//   - SetDeviceProperty appears once, inside guarded_set(), and is poisoned right after it,
//     so no other line in this file can call it.
//   - guarded_set() only accepts settings on kAllowList, inside the director's ranges, with a
//     value the camera currently offers, never after "lock", and never while recording, with two
//     exceptions the director approved: started with --allow-iso-while-recording (Step 7 agent takes),
//     ISO (and nothing else) may change while recording; started with --allow-exposure-while-recording
//     (rehearsal shoots only, 2026-10-20), the allow-listed exposure settings may change while recording.
//   - Commands (record, format, reset, ...) are poisoned for the whole file.
//
// Usage: camera_bridge <socket_path> <log_dir>
//          [--read-only | --allow-iso-while-recording | --allow-exposure | --allow-exposure-while-recording]
//   --read-only: every "set" is refused for the whole run (used in Step 4).
//   --allow-iso-while-recording: Step 7 agent takes only. Off unless given; can't be turned on later.
//   --allow-exposure: aperture f/2.8-f/11, shutter 1/48-1/100 and WB (Auto or Color Temp 2800-7500K)
//     may change too (director, 2026-10-19). Off unless given: ISO only.
//   --allow-exposure-while-recording: rehearsal shoots only. Everything --allow-exposure allows, and it may
//     change while recording too. Off unless given; can't be turned on later.

#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <atomic>
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>

#include "CrImageDataBlock.h"
#include "ICrCameraObjectInfo.h"
#include "IDeviceCallback.h"
#include "sdk_util.hpp"

// Never used anywhere in the bridge. Any mention is a compile error.
#pragma GCC poison SendCommand ExecuteControlCodeValue ExecuteControlCodeString SetDeviceSetting
#pragma GCC poison RequestOperation UploadSettingFile ImportLUTFile SetFTPServerSetting
#pragma GCC poison SetTimeZoneSetting SetMonitoringDeliverySetting ControlMonitoring SetCurrentStr

namespace SDK = SCRSDK;
using namespace sdkutil;

namespace {

const char* kExpectedModel = "ILME-FX2";

// ---------------------------------------------------------------------------
// Allow-list. Director-approved ranges (PROGRESS.md, 2026-10-17 and 2026-10-19).
// ISO is always on the list. Aperture, shutter and white balance (approved
// 2026-10-19) only count when the bridge is started with --allow-exposure.
// Focus and everything else are refused.
// ---------------------------------------------------------------------------
struct AllowRule {
    const char* name;
    CrInt32u code;
    SDK::CrDataType type;
    long long min;
    long long max;
    bool needs_exposure_switch;
};

const AllowRule kAllowList[] = {
    {"IsoSensitivity", SDK::CrDeviceProperty_IsoSensitivity, SDK::CrDataType_UInt32Array, 800, 12800, false},
    {"FNumber", SDK::CrDeviceProperty_FNumber, SDK::CrDataType_UInt16Array, 280, 1100, true},   // f/2.8-f/11 (x100)
    {"ShutterSpeed", SDK::CrDeviceProperty_ShutterSpeed, SDK::CrDataType_UInt32Array, 48, 100, true},  // 1/48-1/100
    {"Colortemp", SDK::CrDeviceProperty_Colortemp, SDK::CrDataType_UInt16, 2800, 7500, true},   // Kelvin
    // WB mode: only Auto (how the director left it) and Color Temp (needed to set Kelvin).
    {"WhiteBalance", SDK::CrDeviceProperty_WhiteBalance, SDK::CrDataType_UInt16Array, SDK::CrWhiteBalance_AWB,
     SDK::CrWhiteBalance_ColorTemp, true},
};

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------
std::atomic<bool> g_running{true};
std::atomic<bool> g_connected{false};
std::atomic<bool> g_locked{false};
std::atomic<bool> g_read_only{false};  // set by --read-only at startup; cannot be turned off
std::atomic<bool> g_iso_while_recording{false};  // --allow-iso-while-recording (Step 7); startup only
std::atomic<bool> g_allow_exposure{false};       // --allow-exposure: aperture, shutter, WB too; startup only
std::atomic<bool> g_exposure_while_recording{false};  // --allow-exposure-while-recording (rehearsal); startup only
SDK::CrDeviceHandle g_handle = 0;
std::mutex g_sdk_mutex;  // one SDK call at a time
std::mutex g_set_mutex;  // one setting change at a time

std::mutex g_log_mutex;
std::ofstream g_log;

void log_event(const std::string& json_fields) {
    std::lock_guard<std::mutex> lock(g_log_mutex);
    g_log << "{\"time\": \"" << now_iso() << "\", " << json_fields << "}\n";
    g_log.flush();
}

// When the camera last reported each setting as changed (steady clock ns).
std::mutex g_change_mutex;
std::map<CrInt32u, long long> g_last_change_ns;

// Result of RequestDisplayStringList: 0 = waiting, 1 = ready, 2 = error.
std::mutex g_ds_mutex;
std::condition_variable g_ds_cv;
int g_ds_state = 0;

struct PropInfo {
    bool found = false;
    CrInt32u type = 0;
    unsigned long long current = 0;
    bool can_set_now = false;
    std::vector<long long> settable;
};

// Read a few settings by code.
std::map<CrInt32u, PropInfo> read_props(std::vector<CrInt32u> codes) {
    std::map<CrInt32u, PropInfo> out;
    std::lock_guard<std::mutex> lock(g_sdk_mutex);
    SDK::CrDeviceProperty* props = nullptr;
    CrInt32 count = 0;
    auto err = SDK::GetSelectDeviceProperties(g_handle, CrInt32u(codes.size()), codes.data(), &props, &count);
    if (CR_FAILED(err) || !props) return out;
    for (CrInt32 i = 0; i < count; ++i) {
        PropInfo info;
        info.found = true;
        info.type = props[i].GetValueType();
        info.current = props[i].GetCurrentValue();
        info.can_set_now = props[i].IsSetEnableCurrentValue();
        info.settable = settable_values(props[i]);
        out[props[i].GetCode()] = info;
    }
    SDK::ReleaseDeviceProperties(g_handle, props);
    return out;
}

bool rule_allows(const AllowRule& rule, long long raw) {
    if (rule.code == SDK::CrDeviceProperty_IsoSensitivity) {
        // Bits 24-31 are ISO mode/extension flags; only plain ISO values are allowed.
        // Also rules out ISO AUTO (0xFFFFFF), which is above the range.
        if ((raw >> 24) != 0) return false;
        long long iso = raw & 0xFFFFFF;
        return iso >= rule.min && iso <= rule.max;
    }
    if (rule.code == SDK::CrDeviceProperty_ShutterSpeed) {
        // Packed numerator (upper 16 bits) / denominator (lower 16). Allowed: 1/max .. 1/min seconds,
        // i.e. num/den between 1/100 and 1/48. Rules out Bulb (0) and "none" (0xFFFFFFFF).
        long long num = (raw >> 16) & 0xFFFF, den = raw & 0xFFFF;
        if ((raw >> 32) != 0 || num < 1 || den < 1) return false;
        return num * rule.min <= den && den <= num * rule.max;
    }
    if (rule.code == SDK::CrDeviceProperty_WhiteBalance) return raw == rule.min || raw == rule.max;  // two modes only
    return raw >= rule.min && raw <= rule.max;
}

// Is `raw` one of the values the camera offers? Lists are checked value by value;
// ranges ("min, max, step") by min/max/step.
bool camera_offers(CrInt32u type, const std::vector<long long>& settable, long long raw) {
    if ((type & SDK::CrDataType_RangeBit) && settable.size() == 3) {
        long long lo = settable[0], hi = settable[1], step = settable[2];
        return raw >= lo && raw <= hi && (step <= 0 || (raw - lo) % step == 0);
    }
    for (long long v : settable)
        if (v == raw) return true;
    return false;
}

std::string refuse(const std::string& name, long long raw, const std::string& reason) {
    log_event("\"event\": \"set_refused\", \"name\": \"" + json_escape(name) + "\", \"value\": " +
              std::to_string(raw) + ", \"reason\": \"" + json_escape(reason) + "\"");
    return "{\"ok\": false, \"refused\": true, \"error\": \"" + json_escape(reason) + "\"}";
}

// ---------------------------------------------------------------------------
// THE ONLY FUNCTION THAT CAN CHANGE THE CAMERA.
// Returns a JSON answer. Waits until the camera reports the new value, and
// measures how long each stage took.
// ---------------------------------------------------------------------------
std::string guarded_set(const std::string& name, long long raw) {
    std::lock_guard<std::mutex> one_at_a_time(g_set_mutex);

    if (g_read_only) return refuse(name, raw, "bridge was started read-only");
    if (g_locked) return refuse(name, raw, "kill switch is on (bridge locked)");
    if (!g_connected) return refuse(name, raw, "camera not connected");

    const AllowRule* rule = nullptr;
    for (const auto& r : kAllowList)
        if (name == r.name) rule = &r;
    if (!rule) return refuse(name, raw, "not on the allow-list");
    if (rule->needs_exposure_switch && !g_allow_exposure)
        return refuse(name, raw, "only ISO may change (bridge started without --allow-exposure)");
    if (!rule_allows(*rule, raw)) return refuse(name, raw, "outside the approved range");

    const CrInt32u rec_code = SDK::CrDeviceProperty_RecordingState;
    auto props = read_props({rule->code, rec_code});
    if (!props[rec_code].found) return refuse(name, raw, "could not read recording state");
    const bool recording = props[rec_code].current != SDK::CrMovie_Recording_State_Not_Recording;
    const bool iso_ok = g_iso_while_recording && rule->code == SDK::CrDeviceProperty_IsoSensitivity;
    if (recording && !iso_ok && !g_exposure_while_recording)     // the allow-list holds exposure settings only
        return refuse(name, raw, "camera is recording");
    const PropInfo& target = props[rule->code];
    if (!target.found) return refuse(name, raw, "could not read current value");
    if (!target.can_set_now) return refuse(name, raw, "camera says this setting can't be changed right now");
    if (!camera_offers(target.type, target.settable, raw)) return refuse(name, raw, "camera doesn't offer this value right now");

    const unsigned long long old_value = target.current;
    if (old_value == (unsigned long long)raw)
        return "{\"ok\": true, \"changed\": false, \"old\": " + std::to_string(old_value) +
               ", \"new\": " + std::to_string(raw) + "}";

    long long t_call = 0, t_return = 0;
    SDK::CrError err;
    {
        std::lock_guard<std::mutex> lock(g_sdk_mutex);
        SDK::CrDeviceProperty prop;
        prop.SetCode(rule->code);
        prop.SetCurrentValue(CrInt64u(raw));
        prop.SetValueType(rule->type);
        t_call = steady_ns();
        err = SDK::SetDeviceProperty(g_handle, &prop);
        t_return = steady_ns();
    }
    if (CR_FAILED(err)) {
        std::ostringstream e;
        e << "SetDeviceProperty failed: 0x" << std::hex << err;
        log_event("\"event\": \"set_failed\", \"name\": \"" + json_escape(name) + "\", \"old\": " +
                  std::to_string(old_value) + ", \"new\": " + std::to_string(raw) + ", \"error\": \"" + e.str() + "\"");
        return "{\"ok\": false, \"error\": \"" + e.str() + "\"}";
    }

    // Wait for the camera to report the new value (up to 3 s).
    long long t_confirm = 0;
    unsigned long long seen = old_value;
    while (steady_ns() - t_call < 3'000'000'000LL) {
        auto now_props = read_props({rule->code});
        if (now_props[rule->code].found) {
            seen = now_props[rule->code].current;
            if (seen == (unsigned long long)raw) {
                t_confirm = steady_ns();
                break;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    long long t_callback = 0;
    {
        std::lock_guard<std::mutex> lock(g_change_mutex);
        auto it = g_last_change_ns.find(rule->code);
        if (it != g_last_change_ns.end() && it->second >= t_call) t_callback = it->second;
    }

    auto ms = [&](long long t) { return t ? std::to_string((t - t_call) / 1e6) : std::string("null"); };
    std::string fields = "\"name\": \"" + json_escape(name) + "\", \"old\": " + std::to_string(old_value) +
                         ", \"new\": " + std::to_string(raw) + ", \"confirmed\": " + (t_confirm ? "true" : "false") +
                         ", \"camera_reports\": " + std::to_string(seen) + ", \"ms_sdk_return\": " + ms(t_return) +
                         ", \"ms_first_callback\": " + ms(t_callback) + ", \"ms_confirmed\": " + ms(t_confirm) +
                         ", \"while_recording\": " + (recording ? "true" : "false");
    log_event("\"event\": \"set\", " + fields);
    return std::string("{\"ok\": ") + (t_confirm ? "true" : "false") + ", \"changed\": true, " + fields + "}";
}

}  // namespace

// From here on, nothing can change camera settings except by calling guarded_set().
#pragma GCC poison SetDeviceProperty SetCurrentValue

namespace {

// ---------------------------------------------------------------------------
// Camera callbacks (arrive on Sony's threads)
// ---------------------------------------------------------------------------
class BridgeCallback : public SDK::IDeviceCallback {
public:
    void OnConnected(SDK::DeviceConnectionVersioin) override {
        std::lock_guard<std::mutex> lock(mutex_);
        g_connected = true;
        cv_.notify_all();
    }
    void OnDisconnected(CrInt32u error) override {
        std::lock_guard<std::mutex> lock(mutex_);
        g_connected = false;
        disconnected_ = true;
        log_event("\"event\": \"disconnected\", \"code\": " + std::to_string(error));
        cv_.notify_all();
    }
    void OnError(CrInt32u error) override {
        std::lock_guard<std::mutex> lock(mutex_);
        error_ = error;
        log_event("\"event\": \"camera_error\", \"code\": " + std::to_string(error));
        cv_.notify_all();
    }
    void OnPropertyChangedCodes(CrInt32u num, CrInt32u* codes) override {
        long long t = steady_ns();
        std::lock_guard<std::mutex> lock(g_change_mutex);
        for (CrInt32u i = 0; i < num; ++i) g_last_change_ns[codes[i]] = t;
    }
    void OnWarning(CrInt32u warning) override {
        if (warning == SDK::CrWarning_RequestDisplayStringList_Success ||
            warning == SDK::CrWarning_RequestDisplayStringList_Error) {
            std::lock_guard<std::mutex> lock(g_ds_mutex);
            g_ds_state = (warning == SDK::CrWarning_RequestDisplayStringList_Success) ? 1 : 2;
            g_ds_cv.notify_all();
            return;
        }
        log_event("\"event\": \"camera_warning\", \"code\": " + std::to_string(warning));
    }
    void OnWarningExt(CrInt32u warning, CrInt32 p1, CrInt32 p2, CrInt32 p3) override {
        log_event("\"event\": \"camera_warning_ext\", \"code\": " + std::to_string(warning) + ", \"params\": [" +
                  std::to_string(p1) + ", " + std::to_string(p2) + ", " + std::to_string(p3) + "]");
    }

    bool wait_connected(int seconds) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(seconds), [&] { return g_connected || error_ != 0; });
        return g_connected;
    }
    void wait_disconnected(int seconds) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(seconds), [&] { return disconnected_; });
    }

private:
    std::mutex mutex_;
    std::condition_variable cv_;
    bool disconnected_ = false;
    CrInt32u error_ = 0;
};

// ---------------------------------------------------------------------------
// Live view: a background loop copies each new frame from Sony's buffer.
// ---------------------------------------------------------------------------
struct LiveView {
    std::mutex mutex;
    std::condition_variable cv;
    std::vector<CrInt8u> jpeg;
    bool have_frame = false;
    CrInt32u frame_no = 0;
    long long t_ns = 0;
    long long polls = 0;
    long long unique_frames = 0;
    long long first_frame_ns = 0;
} g_lv;

void live_view_loop() {
    std::vector<CrInt8u> buffer;
    while (g_running) {
        if (!g_connected) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            continue;
        }
        bool got = false;
        CrInt32u frame_no = 0, size = 0;
        const CrInt8u* data = nullptr;
        SDK::CrImageDataBlock block;
        {
            std::lock_guard<std::mutex> lock(g_sdk_mutex);
            SDK::CrImageInfo info;
            if (CR_SUCCEEDED(SDK::GetLiveViewImageInfo(g_handle, &info)) && info.GetBufferSize() > 0) {
                if (buffer.size() < info.GetBufferSize()) buffer.resize(info.GetBufferSize());
                block.SetSize(CrInt32u(buffer.size()));
                block.SetData(buffer.data());
                if (CR_SUCCEEDED(SDK::GetLiveViewImage(g_handle, &block)) && block.GetImageSize() > 0) {
                    got = true;
                    frame_no = block.GetFrameNo();
                    size = block.GetImageSize();
                    data = block.GetImageData();
                }
            }
        }
        {
            std::lock_guard<std::mutex> lock(g_lv.mutex);
            ++g_lv.polls;
            if (got && (!g_lv.have_frame || frame_no != g_lv.frame_no)) {
                g_lv.jpeg.assign(data, data + size);
                g_lv.frame_no = frame_no;
                g_lv.t_ns = steady_ns();
                if (!g_lv.have_frame || g_lv.unique_frames == 0) g_lv.first_frame_ns = g_lv.t_ns;
                g_lv.have_frame = true;
                ++g_lv.unique_frames;
                g_lv.cv.notify_all();
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
}

// ---------------------------------------------------------------------------
// Command handlers
// ---------------------------------------------------------------------------
std::string cmd_status() {
    std::ostringstream o;
    o << "{\"ok\": true, \"model\": \"" << kExpectedModel << "\", \"connected\": " << (g_connected ? "true" : "false")
      << ", \"locked\": " << (g_locked ? "true" : "false")
      << ", \"read_only\": " << (g_read_only ? "true" : "false")
      << ", \"iso_while_recording\": " << (g_iso_while_recording ? "true" : "false")
      << ", \"exposure_while_recording\": " << (g_exposure_while_recording ? "true" : "false")
      << ", \"allow_exposure\": " << (g_allow_exposure ? "true" : "false") << ", \"allow_list\": [";
    bool first = true;
    for (const auto& r : kAllowList) {
        if (r.needs_exposure_switch && !g_allow_exposure) continue;
        o << (first ? "" : ", ") << "{\"name\": \"" << r.name << "\", \"min\": " << r.min << ", \"max\": " << r.max << "}";
        first = false;
    }
    o << "]}";
    return o.str();
}

std::string props_json(SDK::CrDeviceProperty* props, CrInt32 count) {
    std::string out = "{\"ok\": true, \"time\": \"" + now_iso() + "\", \"properties\": [";
    for (CrInt32 i = 0; i < count; ++i) out += (i ? ", " : "") + property_json(props[i]);
    return out + "]}";
}

std::string cmd_settings() {
    std::lock_guard<std::mutex> lock(g_sdk_mutex);
    SDK::CrDeviceProperty* props = nullptr;
    CrInt32 count = 0;
    if (CR_FAILED(SDK::GetDeviceProperties(g_handle, &props, &count)) || !props)
        return "{\"ok\": false, \"error\": \"GetDeviceProperties failed\"}";
    std::string out = props_json(props, count);
    SDK::ReleaseDeviceProperties(g_handle, props);
    return out;
}

std::string cmd_get(const std::vector<std::string>& names) {
    std::vector<CrInt32u> codes;
    for (const auto& n : names) {
        CrInt32u code;
        if (!property_code(n, &code)) return "{\"ok\": false, \"error\": \"unknown setting: " + json_escape(n) + "\"}";
        codes.push_back(code);
    }
    std::lock_guard<std::mutex> lock(g_sdk_mutex);
    SDK::CrDeviceProperty* props = nullptr;
    CrInt32 count = 0;
    if (CR_FAILED(SDK::GetSelectDeviceProperties(g_handle, CrInt32u(codes.size()), codes.data(), &props, &count)) || !props)
        return "{\"ok\": false, \"error\": \"GetSelectDeviceProperties failed\"}";
    std::string out = props_json(props, count);
    SDK::ReleaseDeviceProperties(g_handle, props);
    return out;
}

std::string cmd_lvstats(bool reset) {
    std::lock_guard<std::mutex> lock(g_lv.mutex);
    double secs = g_lv.unique_frames > 1 ? (g_lv.t_ns - g_lv.first_frame_ns) / 1e9 : 0;
    std::ostringstream o;
    o << "{\"ok\": true, \"polls\": " << g_lv.polls << ", \"unique_frames\": " << g_lv.unique_frames
      << ", \"seconds\": " << secs << ", \"fps\": " << (secs > 0 ? (g_lv.unique_frames - 1) / secs : 0)
      << ", \"last_frame_no\": " << g_lv.frame_no << ", \"last_bytes\": " << g_lv.jpeg.size() << "}";
    if (reset) {
        g_lv.polls = 0;
        g_lv.unique_frames = 0;
    }
    return o.str();
}

std::string cmd_display_strings(long long type_id) {
    {
        std::lock_guard<std::mutex> lock(g_ds_mutex);
        g_ds_state = 0;
    }
    {
        std::lock_guard<std::mutex> lock(g_sdk_mutex);
        auto err = SDK::RequestDisplayStringList(g_handle, SDK::CrDisplayStringType(type_id));
        if (CR_FAILED(err)) return "{\"ok\": false, \"error\": \"RequestDisplayStringList failed: " + std::to_string(err) + "\"}";
    }
    {
        std::unique_lock<std::mutex> lock(g_ds_mutex);
        g_ds_cv.wait_for(lock, std::chrono::seconds(5), [] { return g_ds_state != 0; });
        if (g_ds_state != 1)
            return std::string("{\"ok\": false, \"error\": \"") +
                   (g_ds_state == 2 ? "camera does not support this list" : "no answer within 5 s") + "\"}";
    }
    std::lock_guard<std::mutex> lock(g_sdk_mutex);
    SDK::CrDisplayStringListInfo* list = nullptr;
    CrInt32u num = 0;
    auto err = SDK::GetDisplayStringList(g_handle, SDK::CrDisplayStringType(type_id), &list, &num);
    if (CR_FAILED(err) || !list) return "{\"ok\": false, \"error\": \"GetDisplayStringList failed: " + std::to_string(err) + "\"}";
    std::ostringstream o;
    o << "{\"ok\": true, \"type\": " << type_id << ", \"items\": [";
    for (CrInt32u i = 0; i < num; ++i) {
        std::string text;
        for (CrInt32u k = 0; list[i].displayString && k < list[i].displayStringSize; ++k) {
            char c = char(list[i].displayString[k]);
            if (c == 0) break;
            text += c;
        }
        o << (i ? ", " : "") << "{\"value\": " << list[i].value << ", \"text\": \"" << json_escape(text) << "\"}";
    }
    o << "]}";
    SDK::ReleaseDisplayStringList(g_handle, list);
    return o.str();
}

bool write_all(int fd, const void* data, size_t len) {
    const char* p = static_cast<const char*>(data);
    while (len > 0) {
        ssize_t n = ::write(fd, p, len);
        if (n <= 0) return false;
        p += n;
        len -= size_t(n);
    }
    return true;
}

// "frame" answers with a JSON header line and then the raw JPEG bytes.
bool cmd_frame(int fd, long long after, long long timeout_ms) {
    std::vector<CrInt8u> jpeg;
    CrInt32u frame_no;
    long long t_ns;
    {
        std::unique_lock<std::mutex> lock(g_lv.mutex);
        bool ready = g_lv.cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&] {
            return !g_running || (g_lv.have_frame && (after < 0 || g_lv.frame_no != CrInt32u(after)));
        });
        if (!ready || !g_lv.have_frame) {
            std::string err = "{\"ok\": false, \"error\": \"no new frame within timeout\"}\n";
            return write_all(fd, err.data(), err.size());
        }
        jpeg = g_lv.jpeg;
        frame_no = g_lv.frame_no;
        t_ns = g_lv.t_ns;
    }
    std::string header = "{\"ok\": true, \"frame_no\": " + std::to_string(frame_no) +
                         ", \"age_ms\": " + std::to_string((steady_ns() - t_ns) / 1e6) +
                         ", \"bytes\": " + std::to_string(jpeg.size()) + "}\n";
    return write_all(fd, header.data(), header.size()) && write_all(fd, jpeg.data(), jpeg.size());
}

std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> parts;
    std::istringstream in(line);
    std::string p;
    while (in >> p) parts.push_back(p);
    return parts;
}

bool parse_int(const std::string& s, long long* out) {
    try {
        size_t used = 0;
        *out = std::stoll(s, &used, 0);
        return used == s.size();
    } catch (...) {
        return false;
    }
}

// Handle one command. Returns false if the client connection should close.
bool handle(int fd, const std::string& line) {
    auto args = split(line);
    if (args.empty()) return true;
    const std::string& cmd = args[0];
    std::string reply;
    long long a = 0, b = 0;

    if (cmd == "ping") reply = "{\"ok\": true, \"pong\": true}";
    else if (cmd == "status") reply = cmd_status();
    else if (!g_connected && cmd != "lock" && cmd != "quit") reply = "{\"ok\": false, \"error\": \"camera not connected\"}";
    else if (cmd == "settings") reply = cmd_settings();
    else if (cmd == "get" && args.size() > 1) reply = cmd_get(std::vector<std::string>(args.begin() + 1, args.end()));
    else if (cmd == "frame" && args.size() == 3 && parse_int(args[1], &a) && parse_int(args[2], &b)) return cmd_frame(fd, a, b);
    else if (cmd == "lvstats") reply = cmd_lvstats(args.size() > 1 && args[1] == "reset");
    else if (cmd == "display_strings" && args.size() == 2 && parse_int(args[1], &a)) reply = cmd_display_strings(a);
    else if (cmd == "set" && args.size() == 3 && parse_int(args[2], &a)) reply = guarded_set(args[1], a);
    else if (cmd == "lock") {
        g_locked = true;
        log_event("\"event\": \"locked\"");
        reply = "{\"ok\": true, \"locked\": true}";
    } else if (cmd == "quit") {
        g_running = false;
        reply = "{\"ok\": true, \"quitting\": true}";
    } else reply = "{\"ok\": false, \"error\": \"unknown or malformed command\"}";

    reply += "\n";
    return write_all(fd, reply.data(), reply.size());
}

void client_loop(int fd) {
    std::string pending;
    char buf[4096];
    while (g_running) {
        pollfd p{fd, POLLIN, 0};
        if (::poll(&p, 1, 200) <= 0) continue;
        ssize_t n = ::read(fd, buf, sizeof(buf));
        if (n <= 0) break;
        pending.append(buf, size_t(n));
        size_t pos;
        bool keep = true;
        while (keep && (pos = pending.find('\n')) != std::string::npos) {
            std::string line = pending.substr(0, pos);
            pending.erase(0, pos + 1);
            keep = handle(fd, line);
        }
        if (!keep) break;
    }
    ::close(fd);
}

void on_signal(int) { g_running = false; }

// --check-rules: reads "<Name> <raw>" lines on stdin and prints whether the allow-list would accept
// each value (the exposure switch counted as on). Never connects to a camera; used by the tests to
// check the compiled-in rules against the Python ones.
int check_rules() {
    std::string name;
    long long raw;
    while (std::cin >> name >> raw) {
        const AllowRule* rule = nullptr;
        for (const auto& r : kAllowList)
            if (name == r.name) rule = &r;
        std::cout << name << " " << raw << " " << (rule && rule_allows(*rule, raw) ? 1 : 0) << "\n";
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--check-rules") return check_rules();
    const std::string flag = argc == 4 ? argv[3] : "";
    if (argc < 3 || argc > 4 ||
        (argc == 4 && flag != "--read-only" && flag != "--allow-iso-while-recording" && flag != "--allow-exposure" &&
         flag != "--allow-exposure-while-recording")) {
        std::cerr << "usage: camera_bridge <socket_path> <log_dir> [--read-only | --allow-iso-while-recording | "
                     "--allow-exposure | --allow-exposure-while-recording]\n";
        return 2;
    }
    g_read_only = (flag == "--read-only");
    g_iso_while_recording = (flag == "--allow-iso-while-recording");
    g_exposure_while_recording = (flag == "--allow-exposure-while-recording");
    g_allow_exposure = (flag == "--allow-exposure" || g_exposure_while_recording);
    const std::string socket_path = argv[1];
    g_log.open(std::string(argv[2]) + "/bridge_log.jsonl", std::ios::app);
    ::signal(SIGPIPE, SIG_IGN);
    ::signal(SIGINT, on_signal);
    ::signal(SIGTERM, on_signal);

    if (!SDK::Init()) {
        std::cout << "Sony SDK failed to start\n";
        return 1;
    }
    SDK::ICrEnumCameraObjectInfo* cameras = nullptr;
    if (CR_FAILED(SDK::EnumCameraObjects(&cameras, 5)) || !cameras) {
        std::cout << "No camera found over USB\n";
        SDK::Release();
        return 1;
    }
    const SDK::ICrCameraObjectInfo* target = nullptr;
    int fx2_count = 0;
    for (CrInt32u i = 0; i < cameras->GetCount(); ++i) {
        const SDK::ICrCameraObjectInfo* info = cameras->GetCameraObjectInfo(i);
        if (std::strcmp(info->GetModel(), kExpectedModel) == 0) {
            target = info;
            ++fx2_count;
        }
    }
    if (fx2_count != 1) {
        std::cout << "Expected exactly one " << kExpectedModel << ", found " << fx2_count << ". Stopping.\n";
        cameras->Release();
        SDK::Release();
        return 1;
    }

    BridgeCallback callback;
    if (CR_FAILED(SDK::Connect(const_cast<SDK::ICrCameraObjectInfo*>(target), &callback, &g_handle,
                               SDK::CrSdkControlMode_Remote, SDK::CrReconnecting_OFF)) ||
        !callback.wait_connected(15)) {
        std::cout << "Could not connect to the camera\n";
        cameras->Release();
        SDK::Release();
        return 1;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(1500));  // let the settings list populate
    log_event("\"event\": \"connected\", \"model\": \"" + std::string(kExpectedModel) + "\", \"iso_while_recording\": " +
              (g_iso_while_recording ? "true" : "false") + ", \"allow_exposure\": " + (g_allow_exposure ? "true" : "false") +
              ", \"exposure_while_recording\": " + (g_exposure_while_recording ? "true" : "false"));
    std::cout << "Connected to " << kExpectedModel
              << (g_read_only        ? ". READ-ONLY: all changes refused.\n"
                  : g_allow_exposure ? ". Allow-list: ISO 800-12800, f/2.8-f/11, 1/48-1/100, WB Auto or 2800-7500K.\n"
                                     : ". Allow-list: IsoSensitivity 800-12800 only.\n");
    if (g_iso_while_recording)
        std::cout << "STEP 7 SWITCH ON: ISO (only) may change while the camera records. Restart without it after the take.\n";
    if (g_exposure_while_recording)
        std::cout << "REHEARSAL SWITCH ON: ISO, aperture, shutter and WB may change while the camera records. "
                     "Restart without it afterwards.\n";

    // Private local socket: only programs on this Mac (this user) can connect.
    int server = ::socket(AF_UNIX, SOCK_STREAM, 0);
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, socket_path.c_str(), sizeof(addr.sun_path) - 1);
    ::unlink(socket_path.c_str());
    if (server < 0 || ::bind(server, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0 || ::listen(server, 4) != 0) {
        std::cout << "Could not open socket " << socket_path << "\n";
        g_running = false;
    } else {
        ::chmod(socket_path.c_str(), 0600);
        std::cout << "Listening on " << socket_path << "\n" << std::flush;
    }

    std::thread lv_thread(live_view_loop);
    while (g_running) {
        pollfd p{server, POLLIN, 0};
        if (::poll(&p, 1, 200) <= 0) continue;
        int client = ::accept(server, nullptr, nullptr);
        if (client >= 0) std::thread(client_loop, client).detach();
    }

    std::cout << "Shutting down\n";
    lv_thread.join();
    if (server >= 0) ::close(server);
    ::unlink(socket_path.c_str());
    {
        std::lock_guard<std::mutex> lock(g_sdk_mutex);
        SDK::Disconnect(g_handle);
    }
    callback.wait_disconnected(5);
    SDK::ReleaseDevice(g_handle);
    cameras->Release();
    SDK::Release();
    log_event("\"event\": \"stopped\"");
    std::cout << "Disconnected. Bye.\n";
    return 0;
}
