// SPDX-License-Identifier: GPL-3.0-only
#include "host.hpp"
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <sys/utsname.h>
#include <unistd.h>
#ifdef __APPLE__
#include <pthread.h>
#else
#include <sys/syscall.h>
#endif
#if defined(__x86_64__) || defined(__i386__)
#include <cpuid.h>
#endif
namespace compatlol {
std::string new_run_id() {
    std::random_device random;
    std::ostringstream out;
    for (unsigned i = 0; i < 4; ++i)
        out << std::hex << std::setw(8) << std::setfill('0') << uint32_t(random());
    return out.str();
}
Json log_record(const std::string& run_id, const std::string& severity,
                const std::string& code, const std::string& message) {
    uint64_t tid = 0;
#ifdef __APPLE__
    pthread_threadid_np(nullptr, &tid);
#else
    tid = static_cast<uint64_t>(syscall(SYS_gettid));
#endif
    auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    return {{"schema_version", 1}, {"run_id", run_id}, {"monotonic_ns", ns},
            {"pid", getpid()}, {"tid", tid}, {"component", "host"},
            {"severity", severity}, {"code", code}, {"message", message},
            {"fields", Json::object()}};
}
Json host_report() {
    utsname host{};
    if (uname(&host)) throw std::runtime_error("HOST_UNAME_FAILED");
    Json isa = {{"status", "unknown"}, {"features", Json::array()}};
#if defined(__x86_64__) || defined(__i386__)
    unsigned a = 0, b = 0, c = 0, d = 0;
    if (__get_cpuid(1, &a, &b, &c, &d)) {
        isa["status"] = "observed";
        if (d & (1u << 26)) isa["features"].push_back("sse2");
        if (c & (1u << 0)) isa["features"].push_back("sse3");
        if (c & (1u << 9)) isa["features"].push_back("ssse3");
        if (c & (1u << 19)) isa["features"].push_back("sse4.1");
        if (c & (1u << 20)) isa["features"].push_back("sse4.2");
        // AVX is usable only when CPU, OSXSAVE and OS state management agree.
        bool avx = (c & (1u << 28)) && (c & (1u << 27));
        if (avx) {
            unsigned lo = 0, hi = 0;
            __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
            avx = (lo & 6) == 6;
        }
        if (avx) {
            isa["features"].push_back("avx");
            if (__get_cpuid_count(7, 0, &a, &b, &c, &d) && (b & (1u << 5)))
                isa["features"].push_back("avx2");
        }
    }
#endif
    Json overlay = {{"status", "not-applicable"}, {"supported", nullptr}};
    Json distribution = {{"status", "not-applicable"}, {"id", nullptr}, {"version_id", nullptr}};
#ifdef __linux__
    std::ifstream filesystems("/proc/filesystems");
    overlay["status"] = filesystems ? "observed" : "unavailable";
    if (filesystems) {
        overlay["supported"] = false;
        std::string line;
        while (std::getline(filesystems, line)) {
            std::istringstream fields(line);
            std::string word;
            while (fields >> word) if (word == "overlay") overlay["supported"] = true;
        }
    }
    std::ifstream release("/etc/os-release");
    distribution["status"] = release ? "observed" : "unavailable";
    std::string line;
    while (std::getline(release, line)) {
        auto equals = line.find('=');
        if (equals == std::string::npos) continue;
        auto key = line.substr(0, equals), value = line.substr(equals + 1);
        if (value.size() >= 2 && value.front() == '"' && value.back() == '"')
            value = value.substr(1, value.size() - 2);
        if (key == "ID") distribution["id"] = value;
        if (key == "VERSION_ID") distribution["version_id"] = value;
    }
#endif
    // Environment presence is not evidence of a working server; never expose socket paths.
    Json display = {{"x11_env_present", getenv("DISPLAY") != nullptr},
                    {"wayland_env_present", getenv("WAYLAND_DISPLAY") != nullptr},
                    {"connection", "not-probed"}};
    return {{"schema_version", 1}, {"os", host.sysname}, {"arch", host.machine},
            {"kernel", host.release}, {"distribution", distribution}, {"cpu_isa", isa},
            {"overlayfs", overlay}, {"display", display},
            {"linux_runtime", std::string(host.sysname) == "Linux" ? "unverified" : "blocked"},
            {"vulkan", {{"status", "not-probed"}}},
            {"audio", {{"status", "not-probed"}}}};
}
}
