#include "oad_field_location.h"

#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    assert(argc == 2);
    std::ifstream in(argv[1], std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)), {});
    constexpr size_t header = 80, entry = 1491;
    assert(bytes.size() >= header && (bytes.size() - header) % entry == 0);
    size_t index = 0;
    for (; header + (index + 1) * entry <= bytes.size(); ++index) {
        const char* name = reinterpret_cast<const char*>(bytes.data() + header + index * entry + 1);
        if (std::strcmp(name, "Editable Objects") == 0) break;
    }
    WfOadFieldLocation location{};
    assert(wf_attr_oad_field_location(bytes.data(), bytes.size(), index, 0, &location) == 0);
    assert(location.common_pointer == -1 && location.offset == 572 && location.width == 4);
    assert(wf_attr_oad_field_location(bytes.data(), bytes.size() - 1, index, 0, &location) != 0);
    assert(wf_attr_oad_field_location(nullptr, bytes.size(), index, 0, &location) != 0);
}
