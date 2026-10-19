# Chromecast WebView compatibility

Our current TV web code must work on **Chromium/WebView 91**. On 2026-10-05,
cast2 (`chromecast-test-02`, Android 12) loaded
`com.google.android.webview 91.0.4472.114`; see the
[device log](../diagnostics/bomberman-cast2-input/after/logcat.txt).
Android version, compile/target SDK and a current desktop browser do not establish
the installed WebView's JavaScript/CSS capabilities. Keep this floor until an
intentional support decision and fresh measurements change it.

## The movement regression to remember

Cat-Boom!'s remote movement used `[...held.keys()].at(-1)`. Chrome added `.at()`
in **92**, just above cast2's version. The menu and OK/bomb handlers worked,
while movement threw in the newer API path. Use `keys[keys.length - 1]` instead.
The regression test runs the real bundled game with `Array.prototype.at`
removed, and checks all four directions, hold/release, bombs and pause/resume.
Device recording then confirmed movement from the left spawn corridor across
three cells. [V8's `.at()` support and indexing guidance](https://v8.dev/features/at-method).

## JavaScript operations to write compatibly

These are common traps, not a complete list of every feature added after 91.
Versions below are the first Chrome releases; check Android WebView separately
for APIs that depend on platform integration.

| New API | First Chrome | Compatible approach for our TV code |
| --- | ---: | --- |
| Array, String and TypedArray `.at()` | 92 | Ordinary indexing; last item is `items[items.length - 1]`. Normalize other negative indexes explicitly. String indexing returns UTF-16 code units, as `.at()` does. |
| `Object.hasOwn(obj, key)` | 93 | `Object.prototype.hasOwnProperty.call(obj, key)`; handles null-prototype objects and overridden methods. |
| `new Error(message, {cause})` | 93 | Construct the error, then assign `error.cause = cause` if the caller needs it. Older engines can silently ignore the options argument. |
| `.findLast()` / `.findLastIndex()` | 97 | Scan backward with a loop; return the value or index with the appropriate not-found result. |
| `structuredClone()` | 98 | Clone the known game-state schema explicitly, or use a reviewed fallback. JSON serialization loses undefined, Dates, Maps, typed arrays, cycles and other semantics; it is not a general substitute. |
| `.toSorted()` / `.toReversed()` / `.toSpliced()` / `.with()` | 110 | Copy dense game arrays with `slice()`, then sort/reverse/splice/assign the copy. Validate indexes for `.with()` semantics; sparse-array behavior also differs. |
| `Object.groupBy()` / `Map.groupBy()` | 117 | Loop into `Object.create(null)` or `Map`, creating and appending to each bucket. |
| `Promise.withResolvers()` | 119 | Capture resolve/reject inside `new Promise((resolve, reject) => { ... })`. |

Sources: [V8 9.3 / Chrome 93](https://v8.dev/blog/v8-release-93),
[Chrome 97](https://developer.chrome.com/blog/new-in-chrome-97),
[structuredClone compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/_globals/structuredClone.json),
[array compatibility data](https://github.com/mdn/browser-compat-data/blob/main/javascript/builtins/Array.json),
[Chrome 117 grouping](https://developer.chrome.com/blog/new-in-chrome-117),
[Promise compatibility data](https://github.com/mdn/browser-compat-data/blob/main/javascript/builtins/Promise.json).

## CSS features to provide fallbacks for

| Feature newer than our floor | First Chrome | Compatible approach |
| --- | ---: | --- |
| `:has()` | 105 | Set an explicit parent state class from JavaScript. |
| Size container queries (`@container`) | 105 | Use media queries or a ResizeObserver-driven class for essential layout. |
| `dvh`, `svh`, `lvh` and corresponding viewport units | 108 | Declare `vh`/`vw` fallback first; optionally follow with the newer declaration. For TV, use the fixed available viewport. |
| `color-mix()` | 111 | Precompute and declare an ordinary RGB/hex fallback color first. |
| CSS grid `subgrid` | 117 | Use explicit track sizes or an independent nested grid. |
| `@starting-style` / `transition-behavior: allow-discrete` | 117 | Use class changes and supported opacity/transform transitions; keep showing/hiding controls functional when animation is absent. |

Sources: [Chrome 105](https://developer.chrome.com/blog/new-in-chrome-105),
[Chrome 108](https://developer.chrome.com/blog/new-in-chrome-108),
[Chrome 111](https://developer.chrome.com/blog/new-in-chrome-111),
[Chrome 117](https://developer.chrome.com/blog/new-in-chrome-117).

## Implementation and verification standard

Prefer small compatible operations in hot input/render paths. Feature-detect
optional APIs (`typeof structuredClone === 'function'`) and exercise the fallback.
Unsupported **syntax** can fail before feature detection runs: retain syntax
known to parse in 91, or transpile to that target. Transpilation alone does not
provide missing runtime APIs. Bundle any necessary polyfill locally before the
game script; our offline games cannot depend on a CDN.

Browser API removal tests catch particular missing APIs; they do not emulate
an entire old browser. Test the bundled APK on cast2 through the shared
coordinator, and inspect logs plus visible player movement. Verify startup,
selection, all directions, hold/release, OK, pause and background/resume. A
successful launcher/icon check establishes installation/artwork, not gameplay.

The 2026-10-05 focused sweep of Android source JS/CSS found no further calls to
the listed JavaScript APIs in the shipped Android sources. Bomberman's frozen
browser CSS uses `100dvh`, but its later TV stylesheet explicitly overrides that
rule with supported sizing; retain that override. This focused sweep does not
certify every browser-facing script elsewhere in the repository.
