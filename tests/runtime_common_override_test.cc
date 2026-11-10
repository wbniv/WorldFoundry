#include <pigsys/pigsys.hp>
#include <baseobject/commonblock.hp>
#include <cassert>
#include <cstring>

int main() {
    alignas(4) uint8_t common[16] = {};
    const int32_t shared = 11, changed = 42;
    std::memcpy(common + 4, &shared, 4);
    CommonBlock first(common, sizeof(common)), second(common, sizeof(common));
    std::vector<wfprops::CommonPage> pages;
    first.SetOverrides(&pages);
    pages.push_back({16, std::vector<uint8_t>(4)});
    std::memcpy(pages[0].bytes.data(), &changed, 4);
    int32_t value = 0;
    std::memcpy(&value, first.GetBlockPtr(16), 4); assert(value == 42);
    std::memcpy(&value, first.GetBlockPtr(4), 4); assert(value == 11);
    std::memcpy(&value, second.GetBlockPtr(4), 4); assert(value == 11);
}
