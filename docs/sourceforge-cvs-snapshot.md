# SourceForge `wf-gdk` CVS snapshot

The pre-2010 World Foundry source history is preserved as a CVS repository on SourceForge. This is the **tier-3 fallback** for code archaeology — useful when the current working tree and git history (which begins at commit [`a2784f6`](https://github.com/wbniv/WorldFoundry/commit/a2784f6), 2010-05-01) aren't enough to date a bug, a comment, or a design decision.

## Where to get it

- **Project page:** <https://sourceforge.net/projects/wf-gdk/>
- **Code-snapshot zip (CVS RCS `,v` files):** <https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip>
- **Size:** ~10 MB

```bash
curl -sSL -o /tmp/wf-gdk.zip 'https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip'
mkdir -p /tmp/wf-gdk && (cd /tmp/wf-gdk && unzip -q /tmp/wf-gdk.zip)
```

Layout mirrors the engine + tools tree as of the 2010 GitHub migration. Files retired before migration live in `Attic/` subdirectories (CVS convention for dead files); both live-at-migration and dead-at-migration files have full revision history in their `.cc,v` / `.hp,v` / `.y,v` etc. envelopes.

## Reading `,v` files

The snapshot is raw CVS storage — every `path/file.cc,v` is an RCS file containing the head revision text plus reverse-delta patches for older revisions. There are three usable strategies:

1. **Grep the head text directly.** Each `,v` file's head revision sits as a verbatim block delimited by `@`-quoted strings, so simple `grep -n` on the `,v` file finds patterns in the most-recent revision without needing tooling:
   ```bash
   grep -n 'pattern' /tmp/wf-gdk/wf-gdk/path/to/file.cc,v
   ```
   Good enough for "does the buggy line exist in this revision?" — works for the 99% case.

2. **Read the revision-history header.** Each file's metadata block lists every revision with date and author, in `YYYY.MM.DD.HH.MM.SS` format:
   ```bash
   grep -n -E '^head|^[0-9]+\.[0-9]+$|^date' /tmp/wf-gdk/wf-gdk/path/file.cc,v
   ```
   Quickly answers "when was this file first added?" and "who edited it when?" without checking out anything.

3. **`co -p` (RCS checkout).** If you need a specific older revision as plain text, install the `rcs` package and run `co -p -rN.M file.cc,v > file.cc.revN.M`. Not installed by default on Ubuntu/Debian — `sudo apt install rcs` first.

## Author handles

- `kts` — Kevin T. Seghetti (KTS), the project lead. Almost all pre-2003 revisions.
- `wbniv` — Will Norris. Almost all 2010-05-21 `state dead` commits are his — those mark the migration cut-over when CVS files were closed in favour of the new git repo.

## Notable date facts

- **CVS history begins ~2000-02.** Many core engine + tool files have rev 1.1 dated **2000-02-12** to **2000-02-14** by `kts` — that's the SourceForge CVS import. Earlier provenance (PIGS / pre-SourceForge / PSX-era pre-cleanup) is **not** preserved in CVS; only in-source comments like `// kts 3/27/98 9:45AM` survive as evidence of pre-2000 authorship.
- **Last live edits ~2004.** A handful of files (e.g. `iffcomp/lang.y` rev 1.6) carry late-2003 / 2004 KTS edits; after that, work effectively stopped until the 2010 GitHub migration.
- **Migration cut-over 2010-05-21.** Every file shows a `state dead` revision dated `2010-05-21` by `wbniv` — that's the day the CVS files were retired in favour of the new git repository (git first commit `a2784f6` is `2010-05-01`, but the actual CVS-side cut-over happened three weeks later).

## When to reach for it

In project terms this is **tier 3** of the source-archaeology fallback (see [[project_wfmaxplugins_purged]] memory):

1. **Tier 1 — Working tree.** Anything live in the current checkout.
2. **Tier 2 — `git show <sha>^:<path>`.** Anything deleted in a known git commit (e.g. `wfmaxplugins/*` purged in [`c5761ca`](https://github.com/wbniv/WorldFoundry/commit/c5761ca) on 2026-04-13).
3. **Tier 3 — This snapshot.** Anything retired before the 2010 git import, or anything for which you need a pre-2010 timestamp.

Always try tier 1 first, tier 2 second. The snapshot is for cases where neither covers the question — typically "is this latent bug actually as old as it looks?" or "when did this design decision land relative to the PSX era?"

## Pre-2010 findings cataloged so far

- **`gfx/glpipeline/rendobj3.cc` past-end `&&` short-circuit + `assert(=)` write** ([BUGS.md](BUGS.md)) — rev 1.1 dated 2001-11-24 with both patterns present; parent `gfx/rendobj3.cc` has inline author comment `// kts 3/27/98 9:45AM` putting the sentinel-write pattern at March 1998.
- **`iffcomp/lang.y` broken-arithmetic top-level `+`/`-`** ([BUGS.md](BUGS.md)) — rev 1.1 dated 2000-02-14, pattern is present from the very first revision through `state dead` 2010-05-21. ~26 years latent.
- **`dynamic_cast` introduction in actor containers** ([investigations/2026-04-29-rtti-audit.md](investigations/2026-04-29-rtti-audit.md)) — first appeared in 2003 commits when `Actor*` containers generalised to `BaseObject*` iterators; PSX-era code used `kind()` throughout and had zero `dynamic_cast`.
- **`iffcomp/lang.y` broken arithmetic was never working** ([investigations/2026-04-19-iffcomp-offsetof-arithmetic.md §Postscript 3](investigations/2026-04-19-iffcomp-offsetof-arithmetic.md)) — same shape in 2000-02-14 rev 1.1 as in the modernised grammar, with only a `printf` debug trace observing the computed-but-discarded value. The historical `iff.prp` worked around it via `.offsetof(X, -2048)`.

When you add a finding sourced from the snapshot, append a one-line bullet here with the file, the date you nailed down, and a link to the BUGS.md / investigation entry that used it.
