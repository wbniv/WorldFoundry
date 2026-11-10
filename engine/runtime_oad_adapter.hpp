#pragma once

#include "runtime_properties.hpp"
#include <cstddef>
#include <cstdint>
#include <string>

namespace wfprops {
// Construct the form model from the type's shipped OAD and this object's
// actual payload. firstIndex and payloadOffset describe the omitted prefix of
// a trimmed descriptor. The caller retains ownership of all supplied bytes.
bool buildOadObject(uint32_t actor, const std::string& schema, const std::string& label,
                    const uint8_t* oad, size_t oadLength, uint32_t firstIndex,
                    uint32_t payloadOffset, const uint8_t* payload, size_t payloadLength,
                    const uint8_t* common, size_t commonLength,
                    Object& out, std::string& error);
}
