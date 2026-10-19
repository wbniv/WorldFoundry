# zForth → JS port: target & tooling recommendation

## Recommendation (TL;DR)

**TypeScript, compiled to ES2022 ESM, tested with Vitest, cells stored in an `Int32Array`.**

Reasoning below; the four sub-questions you asked map to the four sections.

---

## 1. Performance: which target & cell storage for the hot inner loop

V8 (and JavaScriptCore in WebKit/Capacitor's WKWebView, and Hermes if WorldFoundry ever goes RN) all tag small integers as **SMIs**: on 64-bit V8, any int in `-2³¹ … 2³¹-1` lives untagged inline. The classic Forth `NEXT`/`EXECUTE` loop is essentially "fetch cell, dispatch, push/pop cell" — exactly the workload SMIs were designed for. ARMv8 even has a dedicated `FJCVTZS` instruction for the float→int32 case JS forces everywhere.

Practical implications:

- Keep every cell value inside the SMI range and the JIT will not box. The idiom `x = (x + y) | 0` is the canonical signal to V8/JSC that "treat this as int32, please" — it produces signed two's-complement wraparound *for free* and matches C's `int32_t` semantics bit-exactly.
- An **`Int32Array` for the data stack, return stack, and dictionary memory** is the right backing store. Reads/writes are guaranteed int32 (the engine elides the tag/untag), the buffer is one contiguous cache-friendly allocation, and you sidestep V8's "holey array" deopts entirely. zForth's C code already treats memory as a flat cell array — `Int32Array` is a near 1:1 mapping.
- **Don't use `BigInt`** for the int32 build — it's heap-allocated, ~50× slower for arithmetic, and you don't need 64-bit range. Reserve `BigInt` only if you later want a 64-bit cell variant.
- **Browser vs Node target doesn't matter for perf** — both run V8 (and JSC on iOS WebView). Choose based on portability: ES2022 ESM runs in both with zero shims, so that's the obvious base layer.

Plain ECMAScript vs TypeScript is a *build-step* question, not a runtime one — TS erases to the same JS.

## 2. Bit-exact C semantics

`number | 0` is the right primitive. It gives signed int32, two's complement, modular wraparound on overflow — identical to `int32_t` arithmetic in C. Division needs explicit `(a / b) | 0` to get C's truncation-toward-zero; `Math.trunc` works but `| 0` is faster and idiomatic in JIT'd code. Use `>>> 0` only where you specifically want the unsigned view (e.g. printing as hex).

`Int32Array[i] = x` performs the same coercion implicitly on store, which is nice — you get the truncation for free at the storage boundary.

`BigInt` is wrong here: you'd lose wraparound (BigInt is arbitrary precision; `(2**31) + 1` does not wrap), and pay 50×+ per op.

## 3. Does TypeScript earn its keep on a port like this?

Yes, modestly — mostly via **branded types**, not classes or interfaces. The single most common port-level bug is exactly the one you named: confusing a cell address (an index into the dictionary memory array) with a cell value (an int that happens to fit in the same range). Brand them — `type Addr = number & { __brand: 'Addr' }`, `type Cell = number & { __brand: 'Cell' }` — and the compiler catches every misuse with zero runtime cost. Same trick for `XT` (execution token) vs `Cell`.

Beyond brands, TS gives you: parameter-count checking on host callbacks (zForth's `zf_host_call` is easy to misuse), exhaustiveness on primitive opcode `switch`, and IDE jump-to-def across the ~30 primitive ops. Build step is ~one `tsconfig.json` and `tsc --watch` — negligible.

For a 1000-line interpreter the ceremony is real but small, and it pays back the first time you mis-index the dictionary.

## 4. Testing framework

**Vitest.** Reasons specific to this project:

- Zero TS config — it just reads `tsconfig.json` and runs.
- Watch mode with HMR feels instant on a small codebase; great for the red-green loop of porting C test vectors.
- Compatible with the same Vite tooling WorldFoundry's browser bundle likely already uses (worth confirming from the WF repo).
- `node:test` is fine for plain JS libs but lacks watch mode and snapshot testing, and needs `tsx` to run TS — net more setup than Vitest, not less.
- Jest is the legacy choice; in 2026 the Vitest ecosystem has caught up and it's 10–20× faster.

Linux desktop setup overhead: `npm i -D vitest` and you're done.

---

## Concrete shape of the port

- Single package, ESM, `"type": "module"`, target `ES2022`, no bundler needed for consumption.
- `src/zforth.ts` — the VM. One `Int32Array` for memory, branded `Addr`/`Cell`/`XT` types, primitive op `switch` using a const enum for opcodes.
- `src/host.ts` — host callback registry; user-supplied JS functions exposed to Forth code via `zf_host_call`.
- `test/` — Vitest specs that mirror zForth's existing test corpus (the C repo has a `.zf` test suite — port verbatim).
- Build: `tsc` only; emit `dist/*.js` + `.d.ts`. Game embedding imports from `dist/` or from source if WF uses Vite.
- One small benchmark harness in `bench/` (Vitest's `bench` API) to track NEXT-loop ns/op as the port stabilises.

## Open questions before coding

1. Cell width: int32 only, or also a float64 variant (zForth's `ZF_CELL_TYPE` knob)? Game scripts may want floats for positions/timers — recommend supporting both via a build flag (separate ES module entry points, not a runtime toggle).
2. Confirm WorldFoundry's bundler (Vite? esbuild? Rollup?) so the ESM target matches.
3. Persistence: zForth has a `zf_save`/`zf_load` for snapshotting the dictionary. Do level scripts need this for save-games?

---

## Sources

- [V8 Internals: How Small is a "Small Integer?"](https://medium.com/fhinkel/v8-internals-how-small-is-a-small-integer-e0badc18b6da)
- [Turbocharging V8 with mutable heap numbers](https://v8.dev/blog/mutable-heap-number)
- [Why ARM Has a JavaScript Instruction (FJCVTZS)](https://notnotp.com/notes/til-why-arm-has-a-js-instruction/)
- [node:test vs Vitest vs Jest (2026)](https://www.pkgpulse.com/blog/node-test-vs-vitest-vs-jest-native-test-runner-2026)
- [Vitest vs Jest 2026: Performance Benchmarks](https://www.sitepoint.com/vitest-vs-jest-2026-migration-benchmark/)
- [TypeScript Branded Types](https://www.learningtypescript.com/articles/branded-types)
- [ts-brand reusable branding helper](https://github.com/kourge/ts-brand)
