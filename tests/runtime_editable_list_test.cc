#include "runtime_editable_list.hpp"
#include <cassert>
#include <vector>

int main() {
    std::vector<uint32_t> indices;
    int32_t list[] = {2, 4, -1};
    assert(wfedit::editableIndices(nullptr, 0, -1, 5, indices) && indices.empty());
    assert(wfedit::editableIndices(list, sizeof(list), 0, 5, indices));
    assert((indices == std::vector<uint32_t>{2, 4}));
    assert(!wfedit::editableIndices(list, sizeof(list) - 4, 0, 5, indices));
    assert(!wfedit::editableIndices(list, sizeof(list), 1, 5, indices));
    assert(!wfedit::editableIndices(list, sizeof(list), 0, 4, indices));
    int32_t duplicates[] = {2, 2, -1};
    assert(!wfedit::editableIndices(duplicates, sizeof(duplicates), 0, 5, indices));

    const char labelsRaw[] = "Cat\0Cats\0";
    std::vector<std::string> labels;
    assert(wfedit::editableLabels(labelsRaw, sizeof(labelsRaw), 0, 2, labels));
    assert((labels == std::vector<std::string>{"Cat", "Cats"}));
    assert(!wfedit::editableLabels(labelsRaw, 7, 0, 2, labels));
    assert(wfedit::editableLabels(nullptr, 0, -1, 0, labels));
    assert(!wfedit::editableLabels(nullptr, 0, -1, 1, labels));

    std::vector<uint8_t> data(104, 0);
    int32_t table[] = {1, 29, 128, 8, 24, 80};
    std::memcpy(data.data(), table, sizeof(table));
    std::vector<wfedit::EditableType> types;
    assert(wfedit::editableTypes(data.data(), data.size(), 0, types));
    assert(types.size() == 1 && types[0].type == 29 && types[0].first == 128 &&
           types[0].payloadOffset == 8 && types[0].oad == data.data() + 24 && types[0].oadLength == 80);
    assert(!wfedit::editableTypes(data.data(), data.size() - 1, 0, types));
    table[0] = 999999; std::memcpy(data.data(), table, sizeof(table));
    assert(!wfedit::editableTypes(data.data(), data.size(), 0, types));
}
