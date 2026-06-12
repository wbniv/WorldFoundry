# Memory Index

- [Party Games project context](project_party_games.md) — Cast-based couch party game on branch `party-games-platform`; Phase 1d blocked on Cast propagation, Phase 2b image game landed.
- [Avoid broad pkill patterns](feedback_process_kill.md) — `pkill -f "node.*index.js"` kills user-started servers too; use specific PIDs or ask.
- [Stage files explicitly when committing](feedback_git_commit_am.md) — `git commit -am` sweeps up pre-existing unrelated deletions (wfsource/, wflevels/); add named files only.
- [Honest about uncertainty](feedback_overclaim.md) — user prefers admitting "I'm guessing" over confident-sounding speculation. Flag hypotheses as hypotheses.
- [Design what was asked, don't propose alternatives](feedback_design_scope.md) — when asked "how do we do X", design X; don't pivot to "you should do Y instead."
- [Treat this as a real business](feedback_business_ops.md) — don't excuse sloppy infra/cred choices with "it's just one person"; apply proper ops hygiene from day one.
- [Cast Developer Console reference](reference_cast_console.md) — cast.google.com/publish; up-to-48h propagation for new app IDs; "Ready For Testing" doesn't mean propagated.
- [World Foundry engine project](project_world_foundry.md) — 3D engine being modernized; scripting mid-migration from Scheme `.s` to zForth (`\ wf`); snowgoons + shell already converted.
- [Dev machine memory constraint](project_dev_machine_memory.md) — laptop is 16GB (2×8 SODIMM, upgradeable to 64GB); ASan wf-edit OOMs running 2 collab instances — use `task build-wf-edit-fast`.
- [WASM editor Rust toolchain](project_wasm_editor_rust_toolchain.md) — browser wf-edit needs isolated rustup 1.85.1 + wasm32-unknown-emscripten + a yrs submodule patch; `task dev-setup-web-edit`.
- [WF level build pipeline](reference_wf_build_pipeline.md) — Blender→.lev→.iff via `wftools/wf_blender/build_level_binary.sh`; engine via `engine/build_game.sh`; run via `wf_game -L <level>.iff`.
- [WF docs/game-ideas/ format](reference_wf_game_ideas_docs.md) — sibling format for arcade-conversion briefs (~150 lines, Wikipedia hero, fixed section list).
- [Verify scripting dialect across multiple files](feedback_verify_scripting_dialect.md) — mid-migration codebases have coexisting dialects; check `.s/.aib/.fth/.lev`-embedded before claiming canonical.
- [User arcade-game familiarity](user_arcade_familiarity.md) — per-game notes on which 1980s titles the user has/hasn't played; ground briefs in Wikipedia/footage, not assumed shared "feel". Bubble Bobble: not played.
- [Run md-to-pdf after writing any .md](feedback_md_to_pdf_after_writes.md) — every Write/Edit on `*.md` should be followed by `task md -- <paths>` without being asked.
- [Asset storefront deficiencies](project_storefront_deficiencies.md) — 13 gaps in the Blender sidebar browser (no grid, no 3D preview, no cart, etc.) captured as requirements for future WF storefront.
- [Include mockups in plans](feedback_mockups.md) — ASCII mockups expected in any plan that describes UI; user has had to ask explicitly multiple times.
- [OAD property paths are scoped, not flat](project_oad_structure.md) — use block.field notation (common.Speed, movebloc.maxVelocity); relevant to scene:set_prop in Phase 2b.
- [Write investigations docs proactively](feedback_investigations.md) — save notable research to docs/investigations/ without asking permission first.
- [Commit freely without asking](feedback_commit_freely.md) — commit at every logical chunk; never ask permission; git is free and rewrites outside git are costly.
- [Replace physics with Jolt](project_followup_replace_physics.md) — Jolt chosen 2026-04-14; CharacterVirtual integrated + parity-tested; open: vehicle constraint, restitution/bounce, substepping.
- [Always link commits in docs](feedback_commit_links.md) — when a doc references a commit hash, include a GitHub link: `https://github.com/wbniv/WorldFoundry/commit/<hash>`.
- [WF camera system origin](project_camera_system.md) — camera is unusually powerful/flexible; evolved from designer indecision, not intentional design. It's a feature.
- [Cross-project glossary location](reference_glossary.md) — `/home/will/SRC/docs/glossary.md` is the canonical glossary; add new terms there, not in memory.
- [Vendor research papers when citing](feedback_vendor_research_papers.md) — SOP: download open-access PDFs into `docs/papers/` (or `engine/<comp>/papers/` for impl refs) in same commit as any doc citing academic work.
- [Use French + Spanish diacritics in prose](feedback_loanword_diacritics.md) — naïve, résumé, façade, déjà vu, jalapeño, El Niño, mañana, señor, etc.; full inventory in the memory file.
- [Code age ≠ stability](feedback_code_age_not_stability.md) — never argue from "N years old / survived untouched"; judge designs on pure CS (ISP/DIP/YAGNI). WF is dormant — don't mention it.
- [Joiner test machine](project_joiner_machine.md) — 192.168.4.32; SSH via Will's keys; runs `task join` for collab testing
- [SSH joiner machine directly](feedback_ssh_joiner.md) — run joiner commands via SSH yourself; don't ask user to do it

<!-- BEGIN GLOBAL MEMORY (managed by claude-housekeeping; do not edit) -->

## User (inherited from ~)

- [user_profile.md](user_profile.md) — Will's role, setup, and desktop/dev preferences
- [user_mammouth_subscription.md](user_mammouth_subscription.md) — €20/mo Mammouth.ai Standard: multi-model API (GPT-4o, Claude, Gemini, Mistral, Llama) at api.mammouth.ai/v1

## Feedback (inherited from ~)

- [feedback_wayland_keybindings.md](feedback_wayland_keybindings.md) — How held modifiers combine with ydotool on GNOME Wayland; architecture for tab switching across apps
- [feedback_wezterm_flatpak.md](feedback_wezterm_flatpak.md) — Use flatpak enter + GUI socket (not flatpak run or mux socket) for WezTerm CLI access
- [feedback_run_task_md.md](feedback_run_task_md.md) — After writing/editing any .md file, run `task md -- {filename}` to preview in browser; never run on non-markdown files
- [feedback_tooling_choices.md](feedback_tooling_choices.md) — Prefer hand-rolled over integration libs when Will already does the pattern manually (e.g., PWA); convert content to Markdown upfront, not "start HTML, migrate later"
- [feedback_bangkok_cost_estimates.md](feedback_bangkok_cost_estimates.md) — Default lower on Bangkok cost estimates; verify against Lalamove/Grab/Makro/local norms, not Western/expat-tier defaults
- [feedback_excluded_providers.md](feedback_excluded_providers.md) — Don't recommend Facebook/Meta (except WhatsApp) or Oracle as providers anywhere; Oracle's "Always Free" ARM tier is mostly fictional (capacity-starved)
- [feedback_no_speculation.md](feedback_no_speculation.md) — Verify before advising: RDAP for domains, file reads for config, the screenshot already on screen — don't list generic "common causes" when state is fetchable
- [feedback_use_task_tracking.md](feedback_use_task_tracking.md) — Reach for TaskCreate/TaskUpdate proactively on multi-step work; don't wait for the auto-reminder
- [feedback_commit_scope.md](feedback_commit_scope.md) — "Commit the others" means the files just enumerated, not everything git status shows; auto-mode doesn't expand scope
- [feedback_md_renderer_no_autolinks.md](feedback_md_renderer_no_autolinks.md) — md-to-pdf.sh silently drops `<url>` autolinks; always use `[url](url)` form
- [feedback_trip_rerender_preview.md](feedback_trip_rerender_preview.md) — In ~/SRC/trip, re-render `task md -- out/currently.md` after every change to the itinerary output
- [feedback_seed_dont_clone.md](feedback_seed_dont_clone.md) — Seeding a new site from an existing one + swapping wordmark/color isn't enough — the source's visual fingerprint carries through. Ship distinctive elements with the seed, not after.
- [feedback_prefer_proper_fix.md](feedback_prefer_proper_fix.md) — When offering fix-scope options, default to the proper/architectural one. Don't lead with the minimal fix as "recommended."
- [feedback_public_vs_internal_surfaces.md](feedback_public_vs_internal_surfaces.md) — Public marketing pages (colophon, homepage) describe visible craft — never internal infra (repo URLs, predecessor projects, deploy pipeline, IaC paths).
- [feedback_node24_everywhere.md](feedback_node24_everywhere.md) — Always use Node 24 on all supported platforms; confirmed: GitHub Actions, Codemagic.io.
- [feedback_always_astro_tailwind.md](feedback_always_astro_tailwind.md) — Always scaffold Astro + Tailwind 4 + @theme tokens even when design is undecided; path choice is infra, not framework.

<!-- END GLOBAL MEMORY -->
