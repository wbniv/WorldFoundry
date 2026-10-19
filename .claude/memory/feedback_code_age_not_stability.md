---
name: feedback-code-age-not-stability
description: "Don't treat code age / \"survived untouched\" as stability or as an argument for/against refactoring; judge designs on pure CS merits. WF is dormant — never mention dormancy."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a737091f-e046-4e46-bbff-43615c95082d
---

When critiquing or recommending changes to WorldFoundry code, **do not use code age or longevity as evidence of anything.** "23 years old", "survived the dead-code purge untouched", "load-bearing stable core" say nothing about correctness, and are not valid arguments for leaving code alone or against reverting/refactoring it. Likewise, "no regression tests so it's risky" is a reason to *add characterization tests as part of the refactor*, not a reason to abstain.

The project has been **dormant** — but **never mention dormancy** in docs or reasoning, and don't lean on it as a premise either. Just drop the age/stability/churn-risk framing entirely.

**Why:** The user pushed back hard on a recommendation built on "23-year-stable core, don't risk churn." Longevity in a dormant codebase is not battle-testing — nothing exercised the code, so age implies neither stability nor correctness. The user wants recommendations derived from "the pure computer science of it all": ISP, DIP, YAGNI, SRP, applied to the actual call graph — not from how long the code has sat there or how scary a change feels.

**How to apply:** Judge a design on its merits. For a class-layer question, the test is "does any client depend on this layer's interface but not on its subclasses?" (DIP/ISP), and "is this member at the lowest-common-ancestor of its callers?" Recommend the principled change and discharge behavior-preservation with tests; don't gate it on age, stability, profiles (unless the change is *purely* performance-motivated), or risk-aversion. See [[feedback_prefer_proper_fix]], [[feedback_overclaim]], and the investigation `docs/investigations/2026-05-30-baseobject-2003-extraction.md`.
