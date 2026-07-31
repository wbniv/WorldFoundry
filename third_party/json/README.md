# nlohmann/json (vendored single header)

`json.hpp` — [nlohmann/json](https://github.com/nlohmann/json) **v3.11.3**,
single-include amalgamation, used by `wf-edit` (M4) to parse `levtree parse`
output into a `wfcrdt::Doc`. Editor-only; never linked into the shipped engine.

- Source: `https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp`
- SHA-256: `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6`
- License: MIT (header carries its own SPDX/notice).

Single committed header rather than a submodule: it is small, header-only, and
has no build step. To update, re-fetch the pinned tag's `single_include` header
and update the SHA above.
