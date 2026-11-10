#include "runtime_oad_adapter.hpp"
#include "oad_field_location.h"
#include <cstring>
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
    Object result; result.actor = actor; result.schema = schema; result.title = label;
    Context context{oad, oadLength, firstIndex, payloadOffset, payload, payloadLength, common, commonLength,
                    &result, &error};
    if (wf_attr_oad_visit(oad, oadLength, visit, &context)) {
        if (error.empty()) error = "malformed OAD descriptor";
        return false;
    }
    out = std::move(result);
    return true;
}
}
