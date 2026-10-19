# Plan: Strip Common Prefix in Outliner Grouped View

## Context

The Outliner's grouped mode (`outliner_group`) clusters actors that share a base name (trailing digits + separator stripped) under a collapsible tree node. When grouping is active the group header already shows the base (e.g. `statplat  (3)`), so repeating it in every child row (`statplat_1`, `statplat_2`, `statplat_3`) is redundant. The user wants an option — defaulting **on** — to strip that shared prefix from children, leaving only the suffix (`_1`, `_2`, `_3`).

## Single file touched

`engine/wf_edit/main.cc`

## Changes (in order, all in one file)

### 1. `WfeditIdentity` struct — add field (line ~121)
```cpp
bool         outliner_group_by_prefix = true;
bool         outliner_strip_prefix    = true;   // ← add
```

### 2. `LoadIdentity` — deserialise (line ~165)
```cpp
id.outliner_group_by_prefix = j.value("outliner_group_by_prefix", true);
id.outliner_strip_prefix    = j.value("outliner_strip_prefix",    true);   // ← add
```

### 3. `SaveIdentity` — serialise (line ~201, inside the `json j{...}` literal)
```cpp
{"outliner_group_by_prefix", id.outliner_group_by_prefix},
{"outliner_strip_prefix",    id.outliner_strip_prefix},    // ← add
```

### 4. `EditorCtx` struct — runtime state (line ~275)
```cpp
bool                     outliner_group        = false;
bool                     outliner_strip_prefix = true;   // ← add
```

### 5. ctx init from identity (line ~2967)
```cpp
ctx.outliner_group        = identity.outliner_group_by_prefix;
ctx.outliner_strip_prefix = identity.outliner_strip_prefix;   // ← add
```

### 6. Save back to identity on exit (line ~3167)
```cpp
identity.outliner_group_by_prefix = ctx.outliner_group;
identity.outliner_strip_prefix    = ctx.outliner_strip_prefix;   // ← add
```

### 7. `render_row` lambda — add optional label param (line ~1785)

Change signature from `[&](int i)` to `[&](int i, const char* label = nullptr)`.

Inside, wrap the `ImGui::Selectable` with `PushID`/`PopID` so suffix-stripped rows (which may not be unique strings) get unique ImGui IDs:

```cpp
auto render_row = [&](int i, const char* label = nullptr) {
    const std::string& eid = ...;
    ...
    ImGui::PushID(i);
    if (ImGui::Selectable(label ? label : c->actor_names[i].c_str(), c->selected == i))
        c->selected = i;
    ImGui::PopID();
    if (peer_sel) { /* dot drawing — uses GetItemRectMin/Max, still valid */ ... }
};
```

### 8. Outliner header — new toggle button (after line 1746)

Only show when grouping is on:

```cpp
if (ImGui::SmallButton(c->outliner_group ? "Ungroup" : "Group"))
    c->outliner_group = !c->outliner_group;
if (c->outliner_group) {
    ImGui::SameLine();
    if (ImGui::SmallButton(c->outliner_strip_prefix ? "Full names" : "Strip prefix"))
        c->outliner_strip_prefix = !c->outliner_strip_prefix;
}
```

### 9. Grouped rendering — pass stripped suffix (lines ~1832-1834)

Replace the simple `for (int i : idx) render_row(i);` loop inside the group with:

```cpp
for (int i : idx) {
    if (c->outliner_strip_prefix) {
        const std::string& name = c->actor_names[i];
        // Strip the shared base; also strip one leading separator (_/-/.)
        // so "statplat_1" → "1", not "_1".
        std::string suffix = name.size() > b.size() ? name.substr(b.size()) : name;
        if (!suffix.empty() && (suffix[0] == '_' || suffix[0] == '-' || suffix[0] == '.'))
            suffix = suffix.substr(1);
        if (suffix.empty()) suffix = name;  // fallback: exact-base names keep full name
        render_row(i, suffix.c_str());
    } else {
        render_row(i);
    }
}
```

Pass-2 unique-base rows are always rendered with the full name (`render_row(members[b][0])` unchanged) because there is no group header to carry the prefix.

## Edge cases handled

| Case | Behaviour |
|---|---|
| `statplat_1`, `statplat_2` (typical) | display `1`, `2` |
| `Player01`, `Player02` | display `01`, `02` |
| `statplat` grouped with `statplat_1` | `statplat` shows full name (empty suffix → fallback) |
| Actor index uniqueness in ImGui | `PushID(i)` before every Selectable |
| Unique-base actors (pass 2) | always full name, strip option has no effect |
| Group mode off | strip option irrelevant; button hidden |

## Verification

1. `task build` — confirm binary timestamp advances.
2. Open wf-edit on any level with multiple `statplat_*` actors.
3. Click **Group** → children should show `_1`, `_2`, … (strip on by default).
4. Click **Full names** → children revert to full names.
5. Toggle back to **Strip prefix** → suffixes return.
6. Quit and reopen — strip preference survives (persisted in `identity.json`).
7. Verify pass-2 unique actors always show full names regardless of strip toggle.
