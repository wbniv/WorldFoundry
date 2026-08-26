| Date | Change |
|------|--------|
| [2026-06-12](https://github.com/wbniv/WorldFoundry/commit/e5d53c08) | feat(web): deploy bundle + fix task build-web; record ASYNCIFY tax |
| [2026-06-11](https://github.com/wbniv/WorldFoundry/commit/6114e500) | docs(investigations): web port — v2 loop inversion is committed scope; add ASYNCIFY tax profiling plan |
| [2026-06-11](https://github.com/wbniv/WorldFoundry/commit/95516a03) | docs(investigations): web/canvas embedding feasibility for wf_game |

<!--history-meta v1
e5d53c08	author	Will Norris
e5d53c08	added	14
e5d53c08	deleted	7
e5d53c08	files	1
e5d53c08	body	- task build-web was broken: emsdk_env.sh has bashisms Task's POSIX shell\n  (mvdan/sh) can't source, so under errexit the build aborted before emcmake\n  ever ran (manual bash builds masked it). Run it through the system bash.\n- task bundle-web: stage build-web/ → dist/web/ (+ index.html) for Cloudflare\n  Pages; web/README.md documents build/run/embed/deploy. dist/ is gitignored.\n- P6.4 ASYNCIFY-tax: filled the investigation's v1 column from measurement —\n  wasm 3.11 MB / 982 KB gz, 3,995 instrumented functions. ASYNCIFY_ONLY/\n  IGNORE_INDIRECT narrowing is NOT viable (HALStart reaches RunGameScript via\n  PIGS function-pointer dispatch → an indirect frame is on the unwind stack),\n  which is the empirical case for the v2 inversion (Phase 7).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
6114e500	author	Will Norris
6114e500	added	48
6114e500	deleted	5
6114e500	files	1
6114e500	body	Per review: state-machine inversion is required (not profiling-contingent)\nbut ships as v2; v1 rides ASYNCIFY. Added profiling section with an A/B\nmeasurement table (naive ASYNCIFY vs ASYNCIFY_ONLY vs inverted), containment\nknobs, and v2 verification steps. Estimate now 3-4 weeks total.\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>
95516a03	author	Will Norris
95516a03	added	186
95516a03	deleted	0
95516a03	files	1
95516a03	body	Emscripten -> wasm + WebGL2 via the existing Android GLES3 path.\nVerdict: high feasibility, est. 2-3 weeks; main refactor is the\nblocking nested main loop (ASYNCIFY for v1). Adds PLATFORMS TODO.\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>
-->
