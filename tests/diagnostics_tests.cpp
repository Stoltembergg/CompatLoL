// SPDX-License-Identifier: GPL-3.0-only
#include "host.hpp"
#include <iostream>
#include <set>
#include <stdexcept>
void require(bool value) { if (!value) throw std::runtime_error("diagnostics assertion failed"); }
int main() {
    try {
        auto id = compatlol::new_run_id();
        require(id.size() == 32);
        require(id.find_first_not_of("0123456789abcdef") == std::string::npos);
        auto first = compatlol::log_record(id, "error", "TEST_REFUSED", "synthetic");
        auto second = compatlol::log_record(id, "error", "TEST_REFUSED", "synthetic");
        for (auto field : {"schema_version", "run_id", "monotonic_ns", "pid", "tid", "component", "severity", "code", "message", "fields"})
            require(first.contains(field));
        require(first["pid"].get<int>() > 0);
        require(first["tid"].get<uint64_t>() > 0);
        require(first["monotonic_ns"].get<int64_t>() <= second["monotonic_ns"].get<int64_t>());
        require(first["fields"].is_object());
        auto host = compatlol::host_report();
        require(host["schema_version"] == 1);
        require(host["cpu_isa"]["features"].is_array());
        std::set<std::string> features;
        for (const auto& feature : host["cpu_isa"]["features"]) require(features.insert(feature.get<std::string>()).second);
        require(!features.count("avx2") || features.count("avx"));
        require(host["vulkan"]["status"] == "not-probed");
        require(host["display"]["connection"] == "not-probed");
        require(compatlol::Json::parse(host.dump()) == host);
        std::cout << "diagnostics contracts passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
