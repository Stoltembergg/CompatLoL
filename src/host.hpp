// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "macho.hpp"
#include <string>
namespace compatlol {
Json host_report();
Json log_record(const std::string& run_id, const std::string& severity,
                const std::string& code, const std::string& message);
std::string new_run_id();
}
