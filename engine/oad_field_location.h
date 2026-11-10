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

#ifdef __cplusplus
}
#endif
#endif
