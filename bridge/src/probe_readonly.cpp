// probe_readonly: first, read-only connection to a Sony ILME-FX2.
//
// What it does, in order:
//   1. Start Sony's SDK and look for cameras on USB.
//   2. Refuse to continue unless exactly one ILME-FX2 is found.
//   3. Connect in Remote mode (no auto-reconnect).
//   4. Read every camera setting and save it to <out_dir>/settings_start.json.
//   5. Copy one live-view frame to <out_dir>/liveview.jpg.
//   6. Read every setting again (<out_dir>/settings_end.json) and report any
//      differences, as proof that nothing was changed.
//   7. Disconnect.
//
// Safety: this program cannot change the camera. The functions that change
// settings or send commands are "poisoned" below: if any line of this file
// used one of them, the build would fail.
//
// Usage: probe_readonly <out_dir>

#include <condition_variable>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>

#include "CrImageDataBlock.h"
#include "ICrCameraObjectInfo.h"
#include "IDeviceCallback.h"
#include "sdk_util.hpp"

// Every Sony call that can change the camera. Any use below is a compile error.
#pragma GCC poison SetDeviceProperty SendCommand ExecuteControlCodeValue ExecuteControlCodeString
#pragma GCC poison SetDeviceSetting RequestOperation UploadSettingFile ImportLUTFile
#pragma GCC poison SetFTPServerSetting SetTimeZoneSetting SetMonitoringDeliverySetting ControlMonitoring
#pragma GCC poison SetCurrentValue SetCurrentStr

namespace SDK = SCRSDK;
using namespace sdkutil;

namespace {

const char* kExpectedModel = "ILME-FX2";

struct PropertySnapshot {
    std::map<CrInt32u, unsigned long long> current;  // code -> current value
    std::map<CrInt32u, std::string> current_str;     // code -> string value (STR types)
    int count = 0;
};

class ProbeCallback : public SDK::IDeviceCallback {
public:
    void OnConnected(SDK::DeviceConnectionVersioin version) override {
        std::lock_guard<std::mutex> lock(mutex_);
        connected_ = true;
        std::cout << "[camera] connected (protocol version " << int(version) << ")\n";
        cv_.notify_all();
    }
    void OnDisconnected(CrInt32u error) override {
        std::lock_guard<std::mutex> lock(mutex_);
        disconnected_ = true;
        std::cout << "[camera] disconnected (code 0x" << std::hex << error << std::dec << ")\n";
        cv_.notify_all();
    }
    void OnError(CrInt32u error) override {
        std::lock_guard<std::mutex> lock(mutex_);
        error_ = error;
        std::cout << "[camera] error 0x" << std::hex << error << std::dec << "\n";
        cv_.notify_all();
    }
    void OnWarning(CrInt32u warning) override {
        std::cout << "[camera] warning 0x" << std::hex << warning << std::dec << "\n";
    }
    void OnWarningExt(CrInt32u warning, CrInt32 p1, CrInt32 p2, CrInt32 p3) override {
        std::cout << "[camera] warning-ext 0x" << std::hex << warning << std::dec
                  << " (" << p1 << ", " << p2 << ", " << p3 << ")\n";
    }

    // Wait until connected; returns false on error or timeout.
    bool wait_connected(int seconds) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(seconds), [&] { return connected_ || error_ != 0; });
        return connected_;
    }
    void wait_disconnected(int seconds) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(seconds), [&] { return disconnected_; });
    }

private:
    std::mutex mutex_;
    std::condition_variable cv_;
    bool connected_ = false;
    bool disconnected_ = false;
    CrInt32u error_ = 0;
};

// Read every property and write it as JSON. Returns a snapshot for comparing later.
bool dump_properties(SDK::CrDeviceHandle handle, const std::string& path, const std::string& camera_json,
                     PropertySnapshot* snapshot) {
    SDK::CrDeviceProperty* props = nullptr;
    CrInt32 count = 0;
    auto err = SDK::GetDeviceProperties(handle, &props, &count);
    if (CR_FAILED(err) || !props) {
        std::cout << "GetDeviceProperties failed: 0x" << std::hex << err << std::dec << "\n";
        return false;
    }

    std::ofstream out(path);
    out << "{\n  \"captured_at\": \"" << now_iso() << "\",\n";
    out << "  \"sdk_version\": \"0x" << std::hex << SDK::GetSDKVersion() << std::dec << "\",\n";
    out << "  \"camera\": " << camera_json << ",\n";
    out << "  \"property_count\": " << count << ",\n  \"properties\": [\n";
    for (CrInt32 i = 0; i < count; ++i) {
        const SDK::CrDeviceProperty& p = props[i];
        snapshot->current[p.GetCode()] = p.GetCurrentValue();
        if (p.GetValueType() == SDK::CrDataType_STR)
            snapshot->current_str[p.GetCode()] = sony_str_to_utf8(p.GetCurrentStr());
        out << "    " << property_json(p) << (i + 1 < count ? "," : "") << "\n";
    }
    out << "  ]\n}\n";
    snapshot->count = count;
    SDK::ReleaseDeviceProperties(handle, props);
    std::cout << "Read " << count << " settings -> " << path << "\n";
    return true;
}

// Copy the newest live-view JPEG. Retries while the first frame is still arriving.
bool save_live_view(SDK::CrDeviceHandle handle, const std::string& path, std::string* info_json) {
    for (int attempt = 0; attempt < 50; ++attempt) {
        SDK::CrImageInfo info;
        auto err = SDK::GetLiveViewImageInfo(handle, &info);
        if (CR_FAILED(err) || info.GetBufferSize() == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        std::vector<CrInt8u> buffer(info.GetBufferSize());
        SDK::CrImageDataBlock block;
        block.SetSize(CrInt32u(buffer.size()));
        block.SetData(buffer.data());
        err = SDK::GetLiveViewImage(handle, &block);
        if (CR_FAILED(err) || block.GetImageSize() == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        std::ofstream out(path, std::ios::binary);
        out.write(reinterpret_cast<const char*>(block.GetImageData()), block.GetImageSize());
        std::ostringstream j;
        j << "{\"file\": \"liveview.jpg\", \"bytes\": " << block.GetImageSize()
          << ", \"info_width\": " << info.GetWidth() << ", \"info_height\": " << info.GetHeight()
          << ", \"buffer_size\": " << info.GetBufferSize() << ", \"frame_no\": " << block.GetFrameNo()
          << ", \"attempts\": " << attempt + 1 << "}";
        *info_json = j.str();
        std::cout << "Saved live view frame (" << block.GetImageSize() << " bytes) -> " << path << "\n";
        return true;
    }
    std::cout << "Could not get a live view frame after 50 attempts\n";
    return false;
}

std::string camera_info_json(const SDK::ICrCameraObjectInfo* info) {
    std::string id;
    const CrInt8u* raw = info->GetId();
    for (CrInt32u i = 0; raw && i < info->GetIdSize(); ++i)
        if (raw[i] >= 0x20 && raw[i] < 0x7F) id += char(raw[i]);
    std::ostringstream j;
    j << "{\"model\": \"" << json_escape(info->GetModel()) << "\""
      << ", \"id\": \"" << json_escape(id) << "\""
      << ", \"connection\": \"" << json_escape(info->GetConnectionTypeName()) << "\""
      << ", \"usb_pid\": " << (info->GetUsbPid() & 0xFFFF) << "}";
    return j.str();
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: probe_readonly <out_dir>\n";
        return 2;
    }
    const std::string out_dir = argv[1];

    std::cout << "probe_readonly: READ-ONLY. This program cannot change camera settings.\n";
    if (!SDK::Init()) {
        std::cout << "Sony SDK failed to start\n";
        return 1;
    }

    int exit_code = 1;
    SDK::ICrEnumCameraObjectInfo* cameras = nullptr;
    auto err = SDK::EnumCameraObjects(&cameras, 5);
    if (CR_FAILED(err) || !cameras || cameras->GetCount() == 0) {
        std::cout << "No camera found over USB (code 0x" << std::hex << err << std::dec << ")\n";
        if (cameras) cameras->Release();
        SDK::Release();
        return 1;
    }

    std::cout << "Cameras found: " << cameras->GetCount() << "\n";
    const SDK::ICrCameraObjectInfo* target = nullptr;
    int fx2_count = 0;
    for (CrInt32u i = 0; i < cameras->GetCount(); ++i) {
        const SDK::ICrCameraObjectInfo* info = cameras->GetCameraObjectInfo(i);
        std::cout << "  [" << i << "] " << info->GetModel() << " via " << info->GetConnectionTypeName() << "\n";
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

    const std::string camera_json = camera_info_json(target);
    ProbeCallback callback;
    SDK::CrDeviceHandle handle = 0;
    err = SDK::Connect(const_cast<SDK::ICrCameraObjectInfo*>(target), &callback, &handle,
                       SDK::CrSdkControlMode_Remote, SDK::CrReconnecting_OFF);
    if (CR_FAILED(err)) {
        std::cout << "Connect failed: 0x" << std::hex << err << std::dec << "\n";
    } else if (!callback.wait_connected(15)) {
        std::cout << "Camera did not confirm the connection within 15 s\n";
    } else {
        // Give the camera a moment to publish its full settings list.
        std::this_thread::sleep_for(std::chrono::milliseconds(1500));

        PropertySnapshot start, end;
        std::string lv_json = "null";
        bool ok = dump_properties(handle, out_dir + "/settings_start.json", camera_json, &start);
        bool lv_ok = save_live_view(handle, out_dir + "/liveview.jpg", &lv_json);
        ok = dump_properties(handle, out_dir + "/settings_end.json", camera_json, &end) && ok;

        // Compare the two reads. Anything that moved is reported, not hidden.
        std::ofstream diff(out_dir + "/probe_result.json");
        diff << "{\n  \"liveview\": " << lv_json << ",\n  \"changed_between_reads\": [";
        int changes = 0;
        for (const auto& [code, value] : end.current) {
            auto it = start.current.find(code);
            bool str_changed = start.current_str.count(code) && start.current_str[code] != end.current_str[code];
            if (it == start.current.end() || it->second != value || str_changed) {
                diff << (changes ? ", " : "") << "{\"name\": \"" << json_escape(property_name(code))
                     << "\", \"start\": " << (it == start.current.end() ? 0ULL : it->second)
                     << ", \"end\": " << value << "}";
                ++changes;
            }
        }
        diff << "],\n  \"property_count_start\": " << start.count << ",\n  \"property_count_end\": " << end.count
             << "\n}\n";
        std::cout << "Settings that differ between first and second read: " << changes << "\n";
        exit_code = (ok && lv_ok) ? 0 : 1;
    }

    if (handle) {
        SDK::Disconnect(handle);
        callback.wait_disconnected(5);
        SDK::ReleaseDevice(handle);
    }
    cameras->Release();
    SDK::Release();
    std::cout << "Done.\n";
    return exit_code;
}
