---
name: Design what was asked, don't propose alternatives
description: When the user asks "how do we do X", design X — don't pivot the answer to "well, you should actually do Y instead"
type: feedback
originSessionId: 6759ec86-6b85-4ff7-ae9e-57b735cd0b2d
---
When the user asks how to integrate / build / wire-up a specific thing, design *that thing*. Do not introduce an architectural alternative they didn't request and then editorialise about which to pick.

**Why:** During the Asteroids/Cast viewport investigation, user asked specifically "how could we incorporate a Chromecast to address the viewport issue for Space Duel" — i.e., add Cast/phones to the WF-native build. I responded with a "Path A vs. Path B" framing, recommended building a separate all-web Asteroids on `party-games-platform` instead, and added a "don't try to merge them" lecture. User pushed back: *"i wasn't trying to merge them at all. just looking to see how we could incorporate a chromecast to address the viewport issues for space duel. fix the plan."* The strategic alternative was unwelcome because it answered a question they hadn't asked.

**How to apply:** When a user asks an integration / how-to question with a clear scope, treat the scope as fixed. Design within it. If a genuinely better path exists, mention it in *one or two sentences* as a follow-up note ("If you ever wanted X instead, that'd look like Y") — not as the headline of the response, not as a recommendation, not as a "the two are different products" framing. Default: trust that the user has thought about scope and is asking what they're asking.
