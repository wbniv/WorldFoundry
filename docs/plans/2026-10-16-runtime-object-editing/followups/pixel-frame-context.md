# Proposal: publish owned touch-frame context

The baseline launches and renders on the Pixel. In the owned touch sessions
J‑9544c851c1d3 and J‑c324a8bad601, the helper rejects the score with
`app-content-changed` before injecting an edge. Display size 2244×1008 and
rotation 1 match, but the screenshot alone does not specify the accessibility
root's bounds. Trying a full display and the inferred app inset rectangle did
not satisfy the strict root-bounds check. These attempts are not picker/form
acceptance.

Keep the existing guard. Add a read-only context result to the owned frame
command: display size, rotation, display ID, foreground package, and the active
accessibility root rectangle captured by the same device helper. Return that
context alongside the PNG and carry its identity into the next score. Also
retain the helper's observed rectangle in rejection evidence; currently its
`app-content-changed:l,t,r,b` detail is truncated to the reason code.

The owner then chooses touch points from the captured PNG and uses the exact
captured context. The helper still rejects focus, size, rotation or root changes
before injection. This is coordinator test tooling, not an engine change. It is
only a proposal in this run; no shared-service or security guard was modified.
