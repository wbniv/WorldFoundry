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
}
