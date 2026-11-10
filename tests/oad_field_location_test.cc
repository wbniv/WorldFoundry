#include "oad_field_location.h"

#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

struct Fields { bool seed = false; bool water = false; };
static int visit(void* context, const WfOadField* field) {
    auto* found = static_cast<Fields*>(context);
    const std::string key(reinterpret_cast<const char*>(field->key.data), field->key.length);
    if (key == "Seed") found->seed = field->kind == 0 && field->live == 1 && field->width == 4;
    if (key == "Water type") {
        const std::string choices(reinterpret_cast<const char*>(field->choices.data), field->choices.length);
        found->water = field->kind == 2 && field->live == 1 && choices == "Freshwater|Saltwater";
    }
    return 0;
}
int main(int argc, char** argv) {
    assert(argc == 3);
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
    bool foundCommon = false;
    for (size_t i = 0; i < (bytes.size() - header) / entry; ++i) {
        if (wf_attr_oad_field_location(bytes.data(), bytes.size(), i, 0, &location) || location.common_pointer < 0) continue;
        uint32_t span = 0;
        assert(wf_attr_oad_common_size(bytes.data(), bytes.size(), i, &span) == 0);
        assert(span >= location.offset + location.width && span % 4 == 0);
        foundCommon = true; break;
    }
    assert(foundCommon);
    std::ifstream schemaFile(argv[2], std::ios::binary);
    std::vector<uint8_t> schema((std::istreambuf_iterator<char>(schemaFile)), {});
    Fields found;
    assert(wf_attr_oad_visit(schema.data(), schema.size(), visit, &found) == 0);
    assert(found.seed && found.water);
    assert(wf_attr_oad_visit(schema.data(), schema.size() - 1, visit, &found) != 0);
}
