// The bridge's start-up switches and kill-switch file, without the Sony SDK or a camera.
// Built and run by tests/test_bridge_args.py. Usage: test_bridge_args <empty scratch folder>
#include <cstdio>
#include <string>
#include <vector>

#include "bridge_args.hpp"

static int failures = 0;
#define CHECK(cond)                                                     \
    do {                                                                \
        if (!(cond)) {                                                  \
            std::printf("FAIL line %d: %s\n", __LINE__, #cond);         \
            ++failures;                                                 \
        }                                                               \
    } while (0)

static std::optional<BridgeArgs> parse(std::vector<const char*> v) {
    v.insert(v.begin(), "camera_bridge");
    return parse_bridge_args(static_cast<int>(v.size()), v.data());
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::string dir = argv[1];

    // What the Mac runs today still works, unchanged.
    auto a = parse({"s.sock", "logs"});
    CHECK(a && a->mode.empty() && a->lock_file.empty());
    a = parse({"s.sock", "logs", "--read-only"});
    CHECK(a && a->mode == "--read-only");
    a = parse({"s.sock", "logs", "--allow-exposure-while-recording"});
    CHECK(a && a->mode == "--allow-exposure-while-recording");

    // The lock file, alone or with a mode, in either order.
    a = parse({"s.sock", "logs", "--lock-file=/data/locked"});
    CHECK(a && a->mode.empty() && a->lock_file == "/data/locked");
    a = parse({"s.sock", "logs", "--read-only", "--lock-file=/data/locked"});
    CHECK(a && a->mode == "--read-only" && a->lock_file == "/data/locked");
    a = parse({"s.sock", "logs", "--lock-file=/data/locked", "--allow-exposure"});
    CHECK(a && a->mode == "--allow-exposure" && a->lock_file == "/data/locked");

    // Refused: never guess what a switch meant.
    CHECK(!parse({"s.sock"}));
    CHECK(!parse({"", "logs"}));
    CHECK(!parse({"s.sock", "logs", "--read-only", "--allow-exposure"}));       // two modes
    CHECK(!parse({"s.sock", "logs", "--read-only", "--read-only"}));            // repeated
    CHECK(!parse({"s.sock", "logs", "--lock-file="}));                          // no path
    CHECK(!parse({"s.sock", "logs", "--lock-file"}));                           // no "="
    CHECK(!parse({"s.sock", "logs", "--lock-file=a", "--lock-file=b"}));        // twice
    CHECK(!parse({"s.sock", "logs", "--allow-everything"}));                    // unknown
    CHECK(!parse({"s.sock", "logs", "--read-only", "--lock-file=a", "--x"}));   // too many

    // The file itself.
    const std::string path = dir + "/locked";
    CHECK(!lock_file_present(""));
    CHECK(!lock_file_present(path));
    CHECK(write_lock_file(path));
    CHECK(lock_file_present(path));
    CHECK(write_lock_file(path));                        // locking twice is fine
    CHECK(!write_lock_file(""));
    CHECK(!write_lock_file(dir + "/no-such-folder/locked"));

    std::printf(failures ? "%d failed\n" : "all passed\n", failures);
    return failures ? 1 : 0;
}
