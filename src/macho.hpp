// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstdint>
#include <vector>
#include <nlohmann/json.hpp>
namespace compatlol {
using Json = nlohmann::json;
Json parse_macho(const std::vector<uint8_t>& bytes);
}
