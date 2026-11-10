#include "runtime_oad_adapter.hpp"
#include "oad_field_location.h"
#include <algorithm>
#include <cstring>
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <sstream>

namespace wfprops {
namespace {
std::string str(WfOadString value) {
    return std::string(reinterpret_cast<const char*>(value.data), value.length);
}
struct Context {
    const uint8_t* oad; size_t oadLength; uint32_t first, prefix;
    const uint8_t* payload; size_t payloadLength;
    const uint8_t* common; size_t commonLength;
    Object* object; std::string* error;
};
struct ApplyContext {
    const uint8_t* oad; size_t oadLength; uint32_t first, prefix;
    std::vector<uint8_t>* payload;
    const uint8_t* common; size_t commonLength;
    std::vector<CommonPage>* pages;
    const std::map<uint32_t, std::string>* values;
    std::string* error;
};
int applyField(void* opaque, const WfOadField* source) {
    auto& ctx = *static_cast<ApplyContext*>(opaque);
    if (source->kind == 3 || source->kind >= 5) return 0;
    if (source->index > std::numeric_limits<uint32_t>::max() - ctx.first) {
        *ctx.error = "descriptor index overflows"; return 1;
    }
    auto value = ctx.values->find(ctx.first + uint32_t(source->index));
    if (value == ctx.values->end()) { *ctx.error = "missing field value"; return 1; }
    WfOadFieldLocation location{};
    if (wf_attr_oad_field_location(ctx.oad, ctx.oadLength, source->index, ctx.prefix, &location) ||
        (location.width != 1 && location.width != 2 && location.width != 4)) {
        *ctx.error = "invalid field location"; return 1;
    }
    char* end = nullptr; errno = 0;
    int64_t raw;
    if (source->kind == 1) {
        const double number = std::strtod(value->second.c_str(), &end);
        const double scaled = number * source->scale;
        if (errno || !end || end == value->second.c_str() || *end || !std::isfinite(scaled) || scaled < INT32_MIN || scaled > INT32_MAX) {
            *ctx.error = "invalid fixed-point value"; return 1;
        }
        raw = std::llround(scaled);
    } else {
        raw = std::strtoll(value->second.c_str(), &end, 10);
        if (errno || !end || *end || end == value->second.c_str()) { *ctx.error = "invalid integer value"; return 1; }
    }
    const int bits = int(location.width * 8);
    const int64_t minimum = -(int64_t(1) << (bits - 1)), maximum = (int64_t(1) << (bits - 1)) - 1;
    if (raw < minimum || raw > maximum) { *ctx.error = "field value outside storage range"; return 1; }
    uint8_t encoded[4]; for (size_t i = 0; i < location.width; ++i) encoded[i] = uint8_t(uint64_t(raw) >> (8 * i));
    uint8_t* base = ctx.payload->data(); size_t available = ctx.payload->size();
    if (location.common_pointer >= 0) {
        const size_t pointer = size_t(location.common_pointer);
        if (pointer > available || available - pointer < 4) { *ctx.error = "common pointer outside payload"; return 1; }
        int32_t offset; std::memcpy(&offset, base + pointer, 4);
        auto page = std::find_if(ctx.pages->begin(), ctx.pages->end(),
                                 [offset](const CommonPage& p) { return p.handle == offset; });
        if (page == ctx.pages->end()) {
            uint32_t size = 0;
            if (offset < 0 || wf_attr_oad_common_size(ctx.oad, ctx.oadLength, source->index, &size) ||
                size_t(offset) > ctx.commonLength || size > ctx.commonLength - size_t(offset) ||
                location.offset > size || location.width > size - location.offset) {
                *ctx.error = "field outside common area"; return 1;
            }
            if (!std::memcmp(ctx.common + offset + location.offset, encoded, location.width)) return 0;
            if (ctx.commonLength > size_t(INT32_MAX) - 3) { *ctx.error = "common area too large"; return 1; }
            const size_t baseHandle = (ctx.commonLength + 3) & ~size_t(3);
            if (ctx.pages->size() > (size_t(INT32_MAX) - baseHandle) / 4) { *ctx.error = "too many common pages"; return 1; }
            const int32_t handle = int32_t(baseHandle + ctx.pages->size() * 4);
            ctx.pages->push_back({handle, std::vector<uint8_t>(ctx.common + offset, ctx.common + offset + size)});
            std::memcpy(base + pointer, &handle, 4);
            page = ctx.pages->end() - 1;
        }
        if (location.offset > page->bytes.size() || location.width > page->bytes.size() - location.offset) {
            *ctx.error = "field outside private common page"; return 1;
        }
        std::memcpy(page->bytes.data() + location.offset, encoded, location.width);
        return 0;
    }
    if (location.offset > available || location.width > available - location.offset) {
        *ctx.error = "field outside payload"; return 1;
    }
    std::memcpy(base + location.offset, encoded, location.width);
    return 0;
}
int visit(void* opaque, const WfOadField* source) {
    auto& ctx = *static_cast<Context*>(opaque);
    // String overlays are deliberately deferred; see R11b in the plan.
    if (source->kind == 3 || source->kind >= 8) return 0;
    Field field;
    field.kind = uint8_t(source->kind); field.show = uint8_t(source->show);
    field.readonly = !source->live; field.minimum = source->minimum; field.maximum = source->maximum;
    field.scale = source->scale; field.width = source->width;
    field.key = str(source->key); field.label = str(source->label); field.help = str(source->help);
    field.group = str(source->group); field.choices = str(source->choices);
    if (source->kind >= 5) { ctx.object->fields.push_back(std::move(field)); return 0; }
    if (source->index > std::numeric_limits<uint32_t>::max() - ctx.first) {
        *ctx.error = "descriptor index overflows"; return 1;
    }
    field.id = ctx.first + uint32_t(source->index);
    WfOadFieldLocation location{};
    if (!field.id || wf_attr_oad_field_location(ctx.oad, ctx.oadLength, source->index, ctx.prefix, &location) ||
        (location.width != 1 && location.width != 2 && location.width != 4)) {
        *ctx.error = "invalid field location for " + field.key; return 1;
    }
    const uint8_t* base = ctx.payload; size_t available = ctx.payloadLength;
    if (location.common_pointer >= 0) {
        const size_t pointer = size_t(location.common_pointer);
        if (pointer > ctx.payloadLength || ctx.payloadLength - pointer < 4) {
            *ctx.error = "common pointer outside payload"; return 1;
        }
        int32_t offset; std::memcpy(&offset, ctx.payload + pointer, 4);
        if (offset < 0 || size_t(offset) > ctx.commonLength) {
            *ctx.error = "common pointer outside common area"; return 1;
        }
        base = ctx.common + offset; available = ctx.commonLength - size_t(offset);
    }
    if (location.offset > available || location.width > available - location.offset) {
        *ctx.error = "field outside payload for " + field.key; return 1;
    }
    int32_t raw = 0;
    if (location.width == 4) std::memcpy(&raw, base + location.offset, 4);
    else if (location.width == 2) { int16_t value; std::memcpy(&value, base + location.offset, 2); raw = value; }
    else { int8_t value; std::memcpy(&value, base + location.offset, 1); raw = value; }
    if (field.kind == 1) {
        if (!field.scale) { *ctx.error = "fixed field has zero scale"; return 1; }
        std::ostringstream text; text << std::setprecision(17) << double(raw) / field.scale;
        field.initial = text.str();
    } else field.initial = std::to_string(raw);
    ctx.object->values.emplace(field.id, field.initial);
    ctx.object->fields.push_back(std::move(field));
    return 0;
}
}

bool buildOadObject(uint32_t actor, const std::string& schema, const std::string& label,
                    const uint8_t* oad, size_t oadLength, uint32_t firstIndex,
                    uint32_t payloadOffset, const uint8_t* payload, size_t payloadLength,
                    const uint8_t* common, size_t commonLength, Object& out, std::string& error) {
    error.clear();
    if (!actor || !oad || !payload || !common) { error = "missing OAD object data"; return false; }
    Object result; result.actor = actor; result.schema = schema; result.title = label; result.oadBacked = true;
    Context context{oad, oadLength, firstIndex, payloadOffset, payload, payloadLength, common, commonLength,
                    &result, &error};
    if (wf_attr_oad_visit(oad, oadLength, visit, &context)) {
        if (error.empty()) error = "malformed OAD descriptor";
        return false;
    }
    out = std::move(result);
    return true;
}

bool applyOadObject(const uint8_t* oad, size_t oadLength, uint32_t firstIndex,
                    uint32_t payloadOffset, uint8_t* payload, size_t payloadLength,
                    const uint8_t* common, size_t commonLength,
                    std::vector<CommonPage>& pages,
                    const std::map<uint32_t, std::string>& values, std::string& error) {
    error.clear();
    if (!oad || !payload || !common) { error = "missing OAD object data"; return false; }
    std::vector<uint8_t> staged(payload, payload + payloadLength);
    std::vector<CommonPage> stagedPages = pages;
    ApplyContext context{oad, oadLength, firstIndex, payloadOffset, &staged, common, commonLength,
                         &stagedPages, &values, &error};
    if (wf_attr_oad_visit(oad, oadLength, applyField, &context)) {
        if (error.empty()) error = "malformed OAD descriptor";
        return false;
    }
    // Existing page buffers keep their addresses: actors may hold pointers to
    // them. Reserve first, then update in place and append newly copied pages.
    pages.reserve(stagedPages.size());
    const size_t oldCount = pages.size();
    for (size_t i = 0; i < oldCount; ++i)
        std::memcpy(pages[i].bytes.data(), stagedPages[i].bytes.data(), pages[i].bytes.size());
    for (size_t i = oldCount; i < stagedPages.size(); ++i) pages.push_back(std::move(stagedPages[i]));
    std::memcpy(payload, staged.data(), payloadLength);
    return true;
}
}
