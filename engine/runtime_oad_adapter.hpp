#pragma once

#include "runtime_properties.hpp"
#include "runtime_oad_common.hpp"
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
                    Object& out, std::string& error,
                    bool allWritable = false, bool allowMissingTail = false);

bool readOadField(const Field& field, const uint8_t* payload, size_t payloadLength,
                  const uint8_t* common, size_t commonLength, const std::vector<CommonPage>& pages,
                  std::string& value);

// Apply a validated draft atomically, copying a shared common page on its first
// write and leaving the level's original common area untouched.
bool applyOadObject(const uint8_t* oad, size_t oadLength, uint32_t firstIndex,
                    uint32_t payloadOffset, uint8_t* payload, size_t payloadLength,
                    const uint8_t* common, size_t commonLength,
                    std::vector<CommonPage>& pages,
                    const std::map<uint32_t, std::string>& values, std::string& error,
                    bool allowMissingTail = false);
}
