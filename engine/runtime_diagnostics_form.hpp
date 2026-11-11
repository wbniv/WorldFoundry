#pragma once
#include "runtime_properties.hpp"

namespace wfoptions {
// Runtime-only UI: the values and text diagnostics are not actor payloads.
wfprops::Object diagnosticsForm(uint32_t actor, const std::string& title,
                                const std::map<std::string, std::string>& memory);
}
