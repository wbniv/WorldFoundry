# Rotation-mailbox defect: CVS introduction on 3 December 2002

The shared Euler scratch value and commit-only-on-C behavior were introduced together in **`actor.cc` CVS revision 1.19, 2002-12-03 21:08:40 UTC, author `kts`**. This is an exact introduction boundary in the preserved source history, rather than a date inferred from a comment or the 2010 Git import. As of 2026-10-06, the defect has survived **23 years and 10 months**.

## Source and method

Downloaded the [SourceForge `wf-gdk` CVS snapshot](https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip) on 2026-10-06. The affected member is `wf-gdk/wfsource/source/game/Attic/actor.cc,v`. `Attic` records the file's retirement during migration, not missing history. The archive contains full RCS metadata and reverse deltas.

Reconstructed all **90 trunk revisions** from 1.90 back to 1.1, plus the initial vendor revision 1.1.1.1. Revisions 1.1–1.18 lack this shared-scratch/yaw-only-commit pattern. All 72 trunk revisions from 1.19–1.90 contain it, allowing for the later setter rename. The last CVS text is byte-for-byte identical to `actor.cc` in Git root commit `a2784f6eff294ee8da27052230216a8d28ddc364`; initial trunk and vendor import text also match each other.

The companion physics history establishes that the original `Rotation(const Euler&)` call was a **setter**, not a readback: it assigns the orientation or reconstructs the internal matrix. Therefore the older spelling already exhibits the same defect; dating it only from the later `SetRotation` spelling would be wrong.

## Verified timeline

| Revision | Recorded UTC timestamp | Author | Rotation-mailbox behavior |
|---|---|---|---|
| 1.1 / 1.1.1.1 | 2000-02-12 07:00:35 | kts | Initial SourceForge import. A/B/C call their respective `SetRotationA/B/C` immediately. No shared Euler scratch. |
| 1.18 | 2002-12-03 19:42:40 | kts | Last revision before this defect. Still calls the three per-axis setters immediately. |
| **1.19** | **2002-12-03 21:08:40** | **kts** | Adds function-wide `static Euler rotationEuler`; A/B update scratch only; C updates scratch and calls `Rotation(rotationEuler)` on its receiving actor. |
| 1.20–1.21 | 2002-12-04 through 2002-12-06 | kts | Same defective sequence and old setter spelling. |
| 1.22 | 2002-12-09 01:21:50 | kts | Renames the yaw-case setter call to `SetRotation(rotationEuler)`; retains shared state and deferred A/B writes. |
| 1.89 | 2003-10-11 00:31:22 | kts | Last live CVS revision; defect remains. |
| 1.90 | 2010-05-21 07:37:20 | wbniv | Marks the file dead for Git migration; text matches the 2010-05-01 Git root import. |

Revision 1.19's log describes the move from Euler/vector physics storage toward matrices for ODE, replacing individual rotation-component accessors with an Euler interface. The diff directly shows the old setters being commented out and the shared scratch value being added. This identifies the refactor that introduced the defect. It does not establish historical gameplay symptoms or how often scripts exercised interleaved axes.

## Saved evidence

All paths below are local copies or reconstructions from the linked SourceForge archive:

- [Provenance and SHA-256 receipt](2026-10-06-rotation-mailbox-cvs/receipt.json).
- [Raw actor RCS history](2026-10-06-rotation-mailbox-cvs/actor.cc,v) and [raw physics RCS history](2026-10-06-rotation-mailbox-cvs/physical.hpi,v).
- [All revision dates, authors, logs and pattern checks](2026-10-06-rotation-mailbox-cvs/revisions.json).
- [Introducing diff: 1.18 → 1.19](2026-10-06-rotation-mailbox-cvs/actor-1.18-to-1.19.diff).
- [Setter rename diff: 1.21 → 1.22](2026-10-06-rotation-mailbox-cvs/actor-1.21-to-1.22.diff).
- Reconstructed [last pre-defect revision](2026-10-06-rotation-mailbox-cvs/actor.cc.rev1.18.txt), [first defective revision](2026-10-06-rotation-mailbox-cvs/actor.cc.rev1.19.txt), and [physics setter at that refactor](2026-10-06-rotation-mailbox-cvs/physical.hpi.rev1.5.txt).
- [RCS reconstruction helper](2026-10-06-rotation-mailbox-cvs/rcs-history.py), which reads archived data and writes a selected revision to stdout.

Reproduce a revision from the repository root:

```sh
python3 docs/investigations/2026-10-06-rotation-mailbox-cvs/rcs-history.py \
  docs/investigations/2026-10-06-rotation-mailbox-cvs/actor.cc,v 1.19 \
  > /tmp/actor-cvs-1.19.cc
```

No engine code was changed. The [BUGS entry](../BUGS.md) now uses the verified CVS introduction date. The runtime repair remains subject to its existing approval and validation requirements.
