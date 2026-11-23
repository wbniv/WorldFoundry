#include "indexed_palette.h"
#include <cassert>
#include <cstdint>
#include <vector>

int main() {
    std::vector<std::uint8_t> data(8 + 2 * wfpalette::kTableBytes, 0);
    data[0] = 'D'; data[1] = 'P'; data[2] = 'L'; data[3] = 'T';
    data[4] = 1; data[6] = 2;
    data[8 + 3 * 123] = 17;
    data[8 + wfpalette::kTableBytes + 3 * 123] = 99;
    wfpalette::Tables tables;
    assert(wfpalette::parse(data.data(), data.size(), tables));
    assert(tables.count == 2 && tables.table(0)[3 * 123] == 17);
    assert(tables.table(1)[3 * 123] == 99 && !tables.table(2));
    assert(tables.color(0, 123)[0] == 17 && tables.color(1, 123)[0] == 99);
    assert(!tables.color(2, 123));
    wfpalette::Selection selection;
    assert(selection.load(data.data(), data.size()));
    assert(selection.count() == 2 && selection.current() == 0);
    const auto revision = selection.revision();
    assert(selection.select(0) && selection.revision() == revision);
    assert(selection.select(1) && selection.colors()[3 * 123] == 99);
    assert(selection.revision() == revision + 1);
    assert(!selection.select(2) && selection.current() == 1);
    assert(!selection.load(data.data(), data.size() - 1));
    assert(selection.current() == 1 && selection.colors()[3 * 123] == 99);
    selection.reset();
    assert(selection.count() == 0 && selection.colors() == nullptr);
    assert(!selection.select(0));
    assert(!wfpalette::parse(data.data(), data.size() - 1, tables));
    assert(tables.count == 0 && tables.bytes == nullptr);
    data[4] = 2;
    assert(!wfpalette::parse(data.data(), data.size(), tables));
    data[4] = 1; data[6] = 0;
    assert(!wfpalette::parse(data.data(), data.size(), tables));
}
