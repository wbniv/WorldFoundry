#ifndef WF_RUNTIME_EDITABLE_LIST_HPP
#define WF_RUNTIME_EDITABLE_LIST_HPP

#include <cstddef>
#include <cstdint>
#include <cstring>
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
}
#endif
