#ifndef WF_RUNTIME_EDITABLE_LIST_HPP
#define WF_RUNTIME_EDITABLE_LIST_HPP

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace wfedit {
// Decode the exported -1-terminated actor index list without reading past the
// level's common area. An absent list (-1) is the normal old-level case.
inline bool editableIndices(const void* common, size_t length, int32_t offset,
                            size_t objectCount, std::vector<uint32_t>& indices) {
    indices.clear();
    if (offset == -1) return true;
    if (!common || offset < 0 || (offset & 3) || size_t(offset) > length) return false;
    const auto* bytes = static_cast<const uint8_t*>(common);
    std::vector<bool> seen(objectCount, false);
    size_t at = static_cast<size_t>(offset);
    while (length - at >= sizeof(int32_t)) {
        int32_t index;
        std::memcpy(&index, bytes + at, sizeof(index));
        at += sizeof(index);
        if (index == -1) return true;
        if (index <= 0 || size_t(index) >= objectCount || seen[index]) return false;
        seen[index] = true;
        indices.push_back(static_cast<uint32_t>(index));
    }
    return false;
}

struct EditableType {
    int32_t type, first, payloadOffset;
    const uint8_t* oad;
    size_t oadLength;
};

// The table has a count followed by (type, first descriptor, prefix bytes,
// OAD offset, OAD length). All offsets are relative to the common area.
inline bool editableTypes(const void* common, size_t length, int32_t offset,
                          std::vector<EditableType>& types) {
    types.clear();
    if (offset == -1) return true;
    if (!common || offset < 0 || (offset & 3) || size_t(offset) > length || length - size_t(offset) < 4) return false;
    const auto* bytes = static_cast<const uint8_t*>(common);
    auto word = [&](size_t at) { int32_t value; std::memcpy(&value, bytes + at, 4); return value; };
    size_t at = size_t(offset);
    int32_t count = word(at); at += 4;
    if (count < 0 || count > 4096 || size_t(count) > (length - at) / 20) return false;
    for (int32_t i = 0; i < count; ++i, at += 20) {
        int32_t type = word(at), first = word(at + 4), prefix = word(at + 8);
        int32_t oadOffset = word(at + 12), oadLength = word(at + 16);
        if (type <= 0 || first < 0 || prefix < 0 || oadOffset < 0 || oadLength < 80 ||
            size_t(oadOffset) > length || size_t(oadLength) > length - size_t(oadOffset) ||
            (size_t(oadLength) - 80) % 1491 != 0) return false;
        for (const auto& previous : types) if (previous.type == type) return false;
        types.push_back({type, first, prefix, bytes + oadOffset, size_t(oadLength)});
    }
    return true;
}

inline bool editableLabels(const void* common, size_t length, int32_t offset,
                           size_t count, std::vector<std::string>& labels) {
    labels.clear();
    if (offset == -1) return count == 0;
    if (!common || offset < 0 || size_t(offset) > length) return false;
    const auto* bytes = static_cast<const char*>(common);
    size_t at = size_t(offset);
    for (size_t i = 0; i < count; ++i) {
        const void* end = std::memchr(bytes + at, 0, length - at);
        if (!end) return false;
        size_t next = static_cast<const char*>(end) - bytes;
        if (next == at) return false;
        labels.emplace_back(bytes + at, next - at);
        at = next + 1;
    }
    return true;
}
}
#endif
