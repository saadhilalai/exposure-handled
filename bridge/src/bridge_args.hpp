// The bridge's start-up switches and its kill-switch file. No Sony SDK in here, so it's tested on its own
// (tests/test_bridge_args.py builds bridge/tests/test_bridge_args.cpp).
//
//   camera_bridge <socket_path> <log_dir> [MODE] [--lock-file=PATH]
//   MODE: at most one of --read-only, --allow-iso-while-recording, --allow-exposure, --allow-exposure-while-recording.
//   --lock-file=PATH: the kill switch outlives a restart (the Pi restarts the bridge by itself after a crash).
//     If PATH exists at start-up, the bridge starts locked. "lock" writes PATH to disk before it answers.
//     The bridge never deletes PATH: unlocking happens outside it, on purpose.
#pragma once

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <optional>
#include <string>

struct BridgeArgs {
    std::string socket_path, log_dir;
    std::string mode;       // "" (ISO only) or one MODE flag
    std::string lock_file;  // "" = the lock lasts until the bridge restarts (the Mac's behaviour)
};

inline bool is_mode_flag(const std::string& a) {
    return a == "--read-only" || a == "--allow-iso-while-recording" || a == "--allow-exposure" ||
           a == "--allow-exposure-while-recording";
}

// Anything unknown, repeated or empty is a usage error: the bridge never guesses what a switch meant.
inline std::optional<BridgeArgs> parse_bridge_args(int argc, const char* const* argv) {
    if (argc < 3 || argc > 5) return std::nullopt;
    BridgeArgs out{argv[1], argv[2], "", ""};
    if (out.socket_path.empty() || out.log_dir.empty()) return std::nullopt;
    const std::string kLock = "--lock-file=";
    bool have_lock = false;
    for (int i = 3; i < argc; ++i) {
        const std::string a = argv[i];
        if (is_mode_flag(a) && out.mode.empty()) {
            out.mode = a;
        } else if (a.rfind(kLock, 0) == 0 && !have_lock && a.size() > kLock.size()) {
            out.lock_file = a.substr(kLock.size());
            have_lock = true;
        } else {
            return std::nullopt;
        }
    }
    return out;
}

inline bool lock_file_present(const std::string& path) {
    struct stat st{};
    return !path.empty() && ::stat(path.c_str(), &st) == 0;
}

// Writes the file and flushes it, and its folder, to the card, so pulling the power right after a kill keeps it.
inline bool write_lock_file(const std::string& path) {
    if (path.empty()) return false;
    int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0) return false;
    const char text[] = "locked by the kill switch\n";
    bool ok = ::write(fd, text, sizeof(text) - 1) == static_cast<ssize_t>(sizeof(text) - 1) && ::fsync(fd) == 0;
    ok = (::close(fd) == 0) && ok;
    const auto slash = path.find_last_of('/');
    const std::string dir = slash == std::string::npos ? "." : (slash == 0 ? "/" : path.substr(0, slash));
    int dfd = ::open(dir.c_str(), O_RDONLY);
    if (dfd >= 0) {
        ::fsync(dfd);
        ::close(dfd);
    }
    return ok && lock_file_present(path);
}
