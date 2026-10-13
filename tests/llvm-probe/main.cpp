// SPDX-License-Identifier: GPL-3.0-only
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <filesystem>
#include <iostream>
#include <set>
#include <iridium/iridium.hpp>
#include <iridium/dynamic-llvm.hpp>
#include <nlohmann/json.hpp>

int main(int argc, char** argv) {
    using Json = nlohmann::json;
    Json result = {{"schema_version", 1}, {"symbol_count", 0}, {"resolved_count", 0},
                   {"missing_symbols", Json::array()}, {"libraries", Json::array()},
                   {"status", "failed"}, {"code", "LLVM_INIT_FAILED"}};
    bool initialized = false;
    try {
        if (argc != 2) throw std::runtime_error("EXPECTED_LIBRARY_REQUIRED");
        if (!Iridium::init()) throw std::runtime_error("LLVM_INIT_FAILED");
        initialized = true;
        std::set<std::string> libraries;
        size_t total = 0, resolved = 0;
#define CHECK_SYMBOL(name) \
        ++total; \
        if (!Iridium::DynamicLLVM::name.isAvailable()) { \
            result["missing_symbols"].push_back(#name); \
        } else { \
            ++resolved; \
            Dl_info location{}; \
            if (!dladdr(Iridium::DynamicLLVM::name.pointer, &location) || !location.dli_fname) \
                throw std::runtime_error("LLVM_LIBRARY_NOT_IDENTIFIED"); \
            libraries.insert(std::filesystem::canonical(location.dli_fname).string()); \
        }
        IRIDIUM_DYNAMICLLVM_FUNCTION_FOREACH(CHECK_SYMBOL)
#undef CHECK_SYMBOL
        result["symbol_count"] = total;
        result["resolved_count"] = resolved;
        result["libraries"] = libraries;
        if (resolved != total) throw std::runtime_error("LLVM_SYMBOLS_MISSING");
        auto expected = std::filesystem::canonical(argv[1]).string();
        if (libraries.size() != 1 || !libraries.count(expected))
            throw std::runtime_error("LLVM_LIBRARY_MISMATCH");
        result["status"] = "passed";
        result["code"] = "OK";
    } catch (const std::filesystem::filesystem_error&) {
        result["code"] = "LLVM_LIBRARY_PATH_UNRESOLVED";
    } catch (const std::exception& error) {
        result["code"] = error.what();
    }
    // once_flag state is not reset: never init/finit/init within this process.
    if (initialized) Iridium::finit();
    std::cout << result.dump() << '\n';
    return result["status"] == "passed" ? 0 : 1;
}
