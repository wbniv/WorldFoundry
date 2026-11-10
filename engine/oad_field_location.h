#ifndef WF_OAD_FIELD_LOCATION_H
#define WF_OAD_FIELD_LOCATION_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct WfOadFieldLocation {
    int32_t common_pointer; /* -1 for an object field; otherwise payload offset */
    uint32_t offset;        /* object offset, or offset inside the common block */
    uint32_t width;
} WfOadFieldLocation;

/* index is relative to the supplied OAD; start_offset accounts for any prefix
 * omitted from a trimmed OAD. Returns 0 on success, 1 for an invalid field. */
int wf_attr_oad_field_location(const uint8_t *oad, size_t oad_len, size_t index,
                               uint32_t start_offset, WfOadFieldLocation *out);
/* Size in bytes of the complete common block containing index; returns 1 if
 * the descriptor is not inside a complete common block. */
int wf_attr_oad_common_size(const uint8_t *oad, size_t oad_len, size_t index,
                            uint32_t *out_size);

/* Strings are UTF-8 pointer/length pairs valid only during the callback. */
typedef struct WfOadString { const uint8_t *data; size_t length; } WfOadString;
typedef struct WfOadField {
    size_t index;
    uint32_t kind, show, live, width, scale;
    int32_t minimum, maximum, default_value;
    WfOadString key, label, help, group, choices;
} WfOadField;
typedef int (*WfOadFieldVisitor)(void *context, const WfOadField *field);

/* Visit visible normalized fields in descriptor order. A visitor returning
 * nonzero stops traversal and makes the function return 1. */
int wf_attr_oad_visit(const uint8_t *oad, size_t oad_len,
                      WfOadFieldVisitor visitor, void *context);

#ifdef __cplusplus
}
#endif
#endif
