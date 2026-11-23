#ifndef WF_INDEXED_PALETTE_H
#define WF_INDEXED_PALETTE_H

#include <cstddef>
#include <cstdint>
#include <vector>

// DPLT v1: magic, LE version, LE table count, then count RGB888 tables.
// The image's index bytes live separately and are never modified by selection.
namespace wfpalette {
constexpr std::size_t kColors = 256;
constexpr std::size_t kTableBytes = kColors * 3;

struct Tables {
    const std::uint8_t* bytes = nullptr;
    std::uint16_t count = 0;

    const std::uint8_t* table(std::size_t index) const {
        return index < count ? bytes + index * kTableBytes : nullptr;
    }

    const std::uint8_t* color(std::size_t tableIndex, std::uint8_t pixelIndex) const {
        const auto* colors = table(tableIndex);
        return colors ? colors + std::size_t(pixelIndex) * 3 : nullptr;
    }
};

inline bool parse(const std::uint8_t* data, std::size_t size, Tables& out) {
    out = {};
    if (!data || size < 8 || data[0] != 'D' || data[1] != 'P' ||
        data[2] != 'L' || data[3] != 'T') return false;
    const unsigned version = unsigned(data[4]) | (unsigned(data[5]) << 8);
    const unsigned count = unsigned(data[6]) | (unsigned(data[7]) << 8);
    if (version != 1 || count == 0 || count > 256 ||
        size != 8 + std::size_t(count) * kTableBytes) return false;
    out.bytes = data + 8;
    out.count = static_cast<std::uint16_t>(count);
    return true;
}

// Own the immutable tables independently of the level's input buffer. The
// revision changes only when the selected colors actually change, so a GPU
// backend can avoid uploading the same table every frame.
class Selection {
public:
    bool load(const std::uint8_t* data, std::size_t size) {
        Tables parsed;
        if (!parse(data, size, parsed)) return false;
        bytes_.assign(parsed.bytes, parsed.bytes + std::size_t(parsed.count) * kTableBytes);
        count_ = parsed.count;
        current_ = 0;
        ++revision_;
        return true;
    }

    bool select(std::size_t index) {
        if (index >= count_) return false;
        if (current_ != index) { current_ = index; ++revision_; }
        return true;
    }

    void reset() {
        if (count_) { bytes_.clear(); count_ = 0; current_ = 0; ++revision_; }
    }

    const std::uint8_t* colors() const {
        return count_ ? bytes_.data() + current_ * kTableBytes : nullptr;
    }
    std::size_t count() const { return count_; }
    std::size_t current() const { return current_; }
    std::uint64_t revision() const { return revision_; }

private:
    std::vector<std::uint8_t> bytes_;
    std::size_t count_ = 0;
    std::size_t current_ = 0;
    std::uint64_t revision_ = 0;
};

inline Selection& active() {
    static Selection value;
    return value;
}
}
#endif
