---
name: Treat this as a real business, not a solo hobby
description: Apply proper operational hygiene — don't excuse sloppy choices with "it's just one person" framing.
type: feedback
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
Don't reason from "you're a solo operator on a personal account, the
difference doesn't really matter" when making operational/security choices.
The user is building a business. The patterns, credentials, and
infrastructure set up *now* are what a second operator or a future employee
or the user-in-three-years will inherit.

**Why:** user explicitly called this out after I handwaved Account vs User
API Tokens as "fine either way for a one-person account." Correct framing is
"use the pattern that survives user turnover and looks right when someone
else reads it," not "pick whichever is faster to click."

**How to apply:** default to the option with proper operational hygiene:
- Account-scoped API tokens over user-scoped, where Cloudflare offers both.
- Narrow token scopes; delete/roll after use.
- Clear naming so a future operator can audit what each token does.
- Scripts as the primary interface; dashboard clicks are the escape hatch,
  not the default.
- Document the "why" in script headers so the setup can be re-derived.

When in doubt, ask what the right operational standard is — don't
pre-dismiss it as overkill for a one-person setup.
