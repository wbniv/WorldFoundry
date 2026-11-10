#pragma once
#include <cstdint>
#include <vector>

namespace wfprops {
// A private page for one actor. The synthetic handle replaces one common-page
// offset in that actor's OAD payload and is resolved by its CommonBlock.
struct CommonPage {
    int32_t handle;
    std::vector<uint8_t> bytes;
};
}
