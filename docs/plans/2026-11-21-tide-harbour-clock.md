# Tide Harbour: the second 3D clock, and the clocks bundle that holds it

**Status: plan for review, 2026‑11‑21.** The level and the bundle are not built. Done so far: the one engine addition, E1 (a date mailbox), is approved and built ([Phase 1 record](#phase-1-record-e1-built)); the Bangkok tide is fitted to the Navy's published predictions and validated on an unseen year ([Phase 0 record](#phase-0-record-the-tide), [research document](../reference/chao-phraya-tide-research.md)). **Approved: D1 to D12 and the answers to Q1 to Q8 at my recommendations, except Q2, which Will answered Thai: the dial uses Thai numerals** (Will, 2026‑11‑21: "accept all except answer to q2 is thai"). Next: the A3 poster (Phase P), and the Phase 0 spikes on cast1. **Runtime control of lights is deliberately not part of this plan** (Will, 2026‑11‑21: "more likely the task is to add control of lights from runtime. today, put it on TODO, and don't use as part of the screensaver implementation for now"); it is its own TODO item.

## Context

Will asked on 2026‑11‑21: "turn Tide harbour entry into the next screensaver in the 3d clock series. we're going to need more animation, i believe / this will be our second 3d clock screensaver / we're gong to implement several of the 50 ideas (each as a separate level) and then bundle them all together info a single cd.iff (i suppose with a menu chooser like the aquarium). when starting as a screensaver, should be able to pass in which clock level to play and not show the chooser menu". While the plan was being researched he added: "we can also move actors in 3d space!!!"

Idea 40 is one of the 50 in the [3D timepieces brainstorm](../../../homeboard-tv/docs/investigations/2026-11-21-3d-timepieces.md#40-tide-harbour), which lives in the Homeboard repository. The whole entry:

> An old Bangkok riverside scene on the Chao Phraya, with wooden stilt houses, piers, traditional boats and a Thai-style clock tower. Its dial shows the time; boats and floating platforms rise and fall with the river's tide.
>
> **Reads:** from the tower dial. **Look for:** the changing water level and boats moving on their moorings. The mockup is concept art; a working clock needs hands that move with the time. Tide predictions for the river remain to be investigated.

![Old Bangkok on the Chao Phraya: stilt houses, piers, boats and a Thai-style clock tower at sunset](../../../homeboard-tv/docs/investigations/2026-11-21-3d-timepieces/40-old-bangkok-clock-tower.png)

That picture is the look to aim at. The plan has two jobs that happen to ship together:

1. **Tide Harbour**, the level: a harbour whose water, boats and sky are a function of the date and the time, with a working clock tower to read.
2. **WF Clocks**, the bundle: one Android app and one `cd.iff` holding every clock level, with a chooser, and a way for a screensaver to name its clock and skip the chooser. Minute Machine becomes the first entry; each later idea is one more level and one more manifest line.

### What the research found

| Question | Finding |
|---|---|
| How does the Aquarium choose? | The Dream picks an index with `TankChoice` (`IDS`, a saved choice, or Random resolved once at start) and passes it to `nativeRun`, which hands the engine the index as its one positional argument ([`TankLaunch.java`](../../android/screensaver/src/main/java/org/worldfoundry/screensaver/TankLaunch.java), [`dream_host.cc`](../../android/screensaver/src/main/cpp/dream_host.cc)). The chooser people see is the **engine's own level menu**: `cdpack --manifest` appends a `MENU` chunk, built from a few lines (`title`, `prompt`, `level <path> \| <name>`), and the engine runs it when the desired level is negative ([`game.cc:306`](../../wfsource/source/game/game.cc), [`aquarium-menu.manifest`](../../wflevels/aquarium-menu.manifest), [level-menu plan](2026-10-01-level-menu-selector.md)). So the chooser needs no new UI code. |
| Where is the gap? | `nativeRun` returns at once for a level below 0 or above 10, so today a Dream can never ask for the menu. It also names the Minute Machine as `player.start(0)` in two places. Both change in Phase 3. |
| Can a script move an actor in 3D? | Yes, and it is how Minute Machine works: 75 actors posed from the wall clock through position, rotation and scale mailboxes, **59.7 FPS on cast1 with no deformers** ([Minute Machine plan](2026-11-21-sixty-second-chain-reaction.md)). That is the animation this plan uses. |
| Is more animation machinery needed? | **No, not for motion.** The expensive kind is the mesh deformer: Seahorse Grid manages 29.6 FPS with 24 deforming meshes, and `DFRM` v1 poses only one curve per mesh ([reef plan](2026-11-02-gulf-of-thailand-reef-tank.md)). A river can be made from many rigid bars (below), which costs what Minute Machine's pieces cost. |
| Can a script change colour or light? | **Not today.** A `Light` actor reads its red, green and blue fields once, when it is built ([`light.cc:51`](../../wfsource/source/game/light.cc)); the clear colour is fixed too. Runtime light control is a separate engine feature, now its own TODO item, and **this plan does not use it**. The day turns to dusk and night with parts that already move: a sliding sky, glow actors and keyed looks ([D5](#decisions)). |
| What does the tide need that the engine lacks? | A **date**. The engine's clock mailboxes carry hour, minute and second only. A tide is set by the Moon: its heights repeat roughly every 24 h 50 min, so the same clock time gives a different water level each day. |
| Where do real predictions come from? | **Found.** The Royal Thai Navy Hydrographic Department posts, for every day, the predicted time and height of each high and low water at 31 stations, as a public PDF per station per year ([2026](https://hydro.navy.mi.th/sevicetide), [2027](https://hydro.navy.mi.th/servicetide2570)). Station **HD, Royal Thai Navy Headquarters**, is on the river inside Bangkok. Heights are metres above the lowest low water and the times are Thai local time, UTC+7, which was **measured** against Ko Lak's observed hourly record (median 11 min at +7 h, 308 min at 0). The Bangkok tide is **mixed, mainly semidiurnal** (form factor 1.36 from our fit; 1.06 in an independent model study), and the year's listed highs and lows run from 0.53 m to 3.33 m. Fitting 64 harmonic constituents to the 2026 table and scoring them on the 2027 table, which the fit never saw, gives a **median error of 4.5 cm** (and 4.1 cm the other way round). The department's own constants are not public, so ours are a fit to its published predictions. Everything, with sources, locators and what was not found, is in the [research document](../reference/chao-phraya-tide-research.md). |

Nothing in this plan states a tidal range, a tide type, a harmonic constant or an error that is not in the [research document](../reference/chao-phraya-tide-research.md) with its source or its script.

## Decisions

Recommendations are in the third column. Nothing is decided until Will answers.

| # | Decision | Recommendation | Alternatives weighed |
|---|---|---|---|
| D1 | How the harbour animates | **Rigid actors only, posed from the clock.** The river is **36 separate bars**, each lifted and tilted by two waves; boats bob, rock and swing on moorings; ropes are stretched bars; hands, sun, moon, clouds, birds and lanterns are more actors. About 100 in all, close to Minute Machine's 75. No new animation machinery | A `DFRM` deformer for the water: one smooth surface, but a deformer per mesh costs far more on cast1 and v1 allows one curve |
| D2 | Where Minute Machine goes | **Into the bundle as level 0.** A new `clocks` flavor, application `org.worldfoundry.clocks`, replaces the `minutemachine` flavor in the same change; cast1 gets the old package uninstalled | Keep both apps: two icons and two screensaver entries for one family |
| D3 | How the clock is chosen | Launcher with no clock named: **the chooser**. `--es clock tide_harbour` on the launcher activity: **straight to that clock**. The Dream: its saved choice (default **Random**, resolved once at start), never the chooser. The settings provider offers the choice | A chooser inside the Dream (a screensaver must never wait for a person) |
| D4 | The order and names of clocks | **Stable ids**, as `TankChoice.IDS`: `minute_machine`, `tide_harbour`. The index is the table-of-contents position; a new clock is appended | Sort alphabetically (an index change would silently re-point saved choices) |
| D5 | How the day turns to night | **No engine change.** A tall gradient mesh for the sky that slides past the camera; glow actors for lamps and windows, moved in front of the dark glass at dusk; and the water, boats and buildings drawn in a few keyed looks (day, dusk, night) cross-faded by moving the lit set forward. Phase 0 shows how well this holds and records the gaps | Runtime light control (a script-writable light colour): would dim everything with one write, but it is an engine feature in its own right and is **deferred to a TODO item, not used here**. Bake one fixed sunset: cheap, but then the look says nothing about the time |
| D6 | The tide itself | **Settled by the research: fitted harmonic constants for Bangkok**, summed in Forth from the date. 64 constituents, median error 4 to 5 cm on an unseen year ([tide_constants.json](../../wflevels/tide_harbour/tide_constants.json)). The department publishes a new table each year, so `task tide-refit` repeats the fit (the years and the file addresses in `tide_fit/` are edited by hand first); the scene needs no nodal correction for the next year (3.7 cm against 3.3 cm) | A synthetic curve (no longer needed); a third-party table (the department's own tables are public and primary) |
| D7 | Frame-rate gate | **At least 30 FPS** on cast1, Release, median over 120 s, the same gate Minute Machine used. Actor budget **150 rigid actors**, measured in Phase 0 on boxes first | A higher gate: the water bars are the likely cost, so measure first |
| D8 | The dial | **Thai numerals ๑ to ๑๒** (Will's answer to Q2), as a Bangkok tower would carry. The cost is legibility across a room, so the digits are drawn large and heavy, and the tower's dial is checked at TV distance in Phase 2. The [harbour mockup](2026-11-21-tide-harbour-clock/harbour.html) shows the problem at its scale: all twelve are small. Two remedies, in order: draw the dial about 1.5 times larger than in the concept art, or carry digits only at ๑๒, ๓, ๖ and ๙ with plain ticks between; if both fail, the concept art's Roman numerals are the fallback | Roman numerals, as in the concept art: more legible, less local |
| D9 | Art style | **Low-poly, flat colour, a few small textures** (roof tile, wood, dial face), built in Blender in the container. Reads as the concept art at a distance and fits the VRAM page | Painterly textures like the concept art: much heavier on the 2048 × 2048 page |
| D10 | Burn-in | **The camera drifts slowly all the time**, as Minute Machine's does; the water, sky and clouds always move, so no pixel sits still | A static camera: the tower dial would burn in |
| D11 | An A3 poster about the tides and the calculation | **Yes, portrait A3 (297 × 420 mm), on the repository's poster pipeline** ([seahorse poster](../reference/seahorse-biomechanics-poster/README.md)): the [research document](../reference/chao-phraya-tide-research.md) first, then `make_poster.py` and `export_poster.py` (PDF, 300 DPI PNG, `layout-review.json`) and a pytest guard. Every claim wears a chip (**verified**, **other source**, **ours (measured)**); the build refuses an unconfirmed claim. See [the poster](#the-poster) | A figure in the plan only: no printable object, and the research would stay buried here |
| D12 | Sun and moon | **No tables, and no claim about the moon.** The sun's rise and set come from a closed-form formula (the sun's declination and the equation of time, for Bangkok's latitude and longitude and the date), a few lines of Forth using the new trig words, and checked in Phase 2 against five published sunrise and sunset times. The moon is only a disc on an arc: its phase and position are **not** claimed, in the scene or on the poster. Will asked (2026‑11‑21): "should we??" about researching sunrise, sunset and moon tables; the answer was no | Tables for every date (a lot of data for a look nobody can check); a fixed 06:00 and 18:00 (seasonal drift is a few tens of minutes, which would pass, but the formula is as cheap and is right); the real moon (phase and position are a project of their own, and the plan's moon-phase stretch is already out of scope) |
| D13 | A settings object in every clock level | **Decided** (Will, 2026‑11‑21: "make sure level has a settings object (same for all clocks---audit)"). Every clock level carries one settings object, built the same way for all clocks: an `.oas` type that includes `settings.inc` with live fields, one instance placed in the level, read by the director with `property@`, a TV form and a phone Dream form both generated from its `.oad`, and a test that edits and checks every live field. [`scripts/audit-clock-settings.py`](../../scripts/audit-clock-settings.py) checks all six and is run in verification. The audit found **no clock has one yet**: see [Settings objects](#settings-objects) | A settings object only where a clock needs options today (what Minute Machine did; it leaves each later clock to decide, and the phone form and the chooser then differ clock to clock) |

## Questions for Will: answered

**Answered 2026‑11‑21** (Will, 2026‑11‑21: "accept all except answer to q2 is thai"). Every recommendation was accepted except Q2. No engine permission is pending: E1 is approved and built, and light control is deferred.

| # | Question | Answer |
|---|---|---|
| Q1 | Accept D1 to D12 as written? | ~~Accept all.~~ **Accepted**, with D8 changed by Q2. |
| Q2 | Dial numerals (D8)? | **Thai numerals ๑ to ๑๒** (not the recommended Roman). |
| Q3 | Art style (D9)? | ~~Low-poly flat colour with a few small textures.~~ **Accepted.** |
| Q4 | Retire the Minute Machine app and uninstall its package from cast1? | ~~Yes, in the same change.~~ **Accepted.** |
| Q5 | Poster language? | ~~English only for now.~~ **Accepted.** |
| Q6 | Tide size on screen? | ~~True to scale against the pier and the gauge board.~~ **Accepted.** |
| Q7 | A TV outside Thailand? | ~~Device time everywhere, as if Thai.~~ **Accepted.** |
| Q8 | Attribution for the tide? | ~~Credit the department; no further step.~~ **Accepted.** |

### Open

| # | Question | Recommendation | What it blocks |
|---|---|---|---|
| Q9 | **What do all clocks share in their settings?** (Will, 2026‑11‑21: "make sure level has a settings object (same for all clocks---audit)") A common `Clock` sheet every clock's settings type includes, and each clock's own fields beside it. | Common: **Camera drift** (Slow, the default, or Off), the burn-in guard Minute Machine's D10 called "push-in". Minute Machine's own: **Hour format** (24 hours by default, or 12). Tide Harbour's own: **Dial numerals** (Thai by default, Roman, or none), **Gauge board** (on or off), **Boats and birds** (on or off). The first release ships these and no more. | The `.oas` files, Phases 2 and 2b |

Optional, not blocking: which of the other 48 ideas comes after Tide Harbour.

## Approach

### The pose-from-clock design, again

Nothing is simulated. A screensaver can start at any moment, so every piece's pose is a **pure function of the date and the time**, computed fresh each frame by the director script, exactly as Minute Machine does. The motions that are not tied to the tide or the hands (ripples, bobbing, birds, clouds) take their phase from the time of day too, so they are repeatable and testable.

```mermaid
flowchart LR
    W["Wall clock<br/>hour, minute, second"] --> D
    DT["Date and UTC offset<br/>(E1, new)"] --> T["tide-m<br/>harmonic sum"]
    DT --> S["sun-hours<br/>sunrise and sunset by day of year"]
    T --> D["Director script<br/>zForth, one pass a frame"]
    S --> D
    W --> S
    D --> P1["Hands<br/>hour, minute, second"]
    D --> P2["Water bars x 36<br/>lift and tilt"]
    D --> P3["Boats, raft, ropes, gauge<br/>ride the tide"]
    D --> P4["Sun, moon, clouds, birds,<br/>lanterns, windows"]
    D --> P5["Look of the day<br/>(sliding sky, glow actors)"]
    P1 & P2 & P3 & P4 & P5 --> R["Engine renders<br/>actors in 3D"]
```

### The river from rigid bars

The water is a stack of 36 long thin boxes, near to far, slightly overlapping. Each is posed every frame with its own height and tilt: two travelling waves added together, scaled up toward the camera so far water looks calm and near water looks lively. The whole river's mean level rides the tide, and a few of the bars also carry a glint that brightens and fades. The [live mockup](2026-11-21-tide-harbour-clock/harbour.html) does exactly this in flat form (tick "outline the water bars" to see them), and its counter says how many actors it poses.

[![The harbour at sunset with controls for the hour, low and high tide, and a tide curve underneath](2026-11-21-tide-harbour-clock/harbour.png)](2026-11-21-tide-harbour-clock/harbour.html)

**Risk, stated plainly:** flat bars may look banded on a 1080p TV, where the concept art is smooth. Phase 0 builds the 36 bars as plain boxes and looks at them on the real TV before anything else is made. The fallback, if it fails, is to raise the count (the budget allows about 150) or to use one `DFRM` mesh for the water alone and pay for that one deformer.

### The tide and the sun

- **Tide:** `tide-m` sums the 64 fitted waves, `amplitude × cos(2π × (cycles per hour × hours + phase))`, plus the mean level, with `hours` counted from 2026‑01‑01 00:00 Thai time. The four that define the tide are K1 (50.0 cm, 23.93 h), M2 (36.3 cm, 12.42 h), O1 (30.9 cm, 25.82 h) and S2 (23.1 cm, 12.00 h); the other 60 add the annual cycle, the other lunar and solar terms, and the shallow-water compound tides a river makes. Fewer would do for the look (12 waves leave a median error of 21 cm; 48 leave 5.6 cm), and the tide only needs evaluating about once a second, so 64 cosines is cheap. The date supplies the phase: `WALL_DAY` minus the epoch's day number, times the cycles per day, plus the hour. A float cell holds about seven digits, so Phase 2 measures the real float error against the table and records it; it is expected to stay under a centimetre.
- **Time zone:** the constants are for Thai local time (UTC+7, no daylight saving). E1 also exposes the device's UTC offset, so a TV elsewhere still shows Bangkok's tide at the right Bangkok moment, or can be told otherwise by a setting later.
- **Sun and moon:** by [D12](#decisions), the sun's rise and set follow from its declination and the equation of time for Bangkok and the date, computed in Forth with the trig words, and checked in Phase 2 against five published times; no table is stored. The moon is a disc on an arc, rising opposite the sun, with no claim about its phase or position.
- **What the tide moves:** the river's mean level, the boats on their ropes (the rope lengths change), the raft between its posts, the water hyacinth drifting up and down the bank, and a **tide gauge board** on a pier post with a pointer, so the tide can be read as well as seen.

### The clock tower

The dial is the one thing that tells the time, and carries **Thai numerals ๑ to ๑๒** (D8). The hour, minute and second hands are three actors turned by the clock, the second hand sweeping. Under the dial, the arch glows at dusk. The tower is the tallest thing in the frame and is lit even at night, so the dial stays readable ([moments](#moments)).

### Moments

[![Six moments from dawn to deep night, each a different tide and a different light](2026-11-21-tide-harbour-clock/moments.png)](2026-11-21-tide-harbour-clock/moments.html)

Six frozen moments from the same code: dawn at low tide, noon, the sunset of the concept art, dusk, night and deep night at another tide. The sky, the water colour, the lit windows and lanterns, and the water level all change with the clock, which is what makes the picture say what time it is even without reading the dial. The mockups draw the day's light freely; how closely the engine's existing moving parts can match them, with no light control, is what the Phase 0 spike must show.

### The poster

Will asked (2026‑11‑21): "update plan: make an a3 poster about the tides and calculations/etc". It is a printable object in its own right, and it makes the research readable. The [mockup](2026-11-21-tide-harbour-clock/poster.html) draws the layout on the real data: panels 1, 4 and 5 are the shipped constants against the Navy's printed events, the out-of-sample errors and the Ko Lak clock check; panel 6 is a placeholder for the finished harbour.

[![A3 portrait poster in seven panels: two highs a day or one, a sum of waves, from a table to constants, how good, which clock, what the harbour does, what we do not know](2026-11-21-tide-harbour-clock/poster.png)](2026-11-21-tide-harbour-clock/poster.html)

- **Content (seven panels):** two highs a day or only one, on three real days; a tide as a sum of waves (K1, O1, M2, S2 and their sum); from a table of highs and lows to constants (the fit); how good it is, against the number of waves kept, on a year the fit never saw; which clock the table uses (the Ko Lak check); what the harbour does with the number; and what we do not know.
- **Rules, from the seahorse poster:** the research document comes first and gives each source's locator and access limits; every printed claim wears a chip (**verified**, **other source**, **ours (measured)**); claims the research could not confirm stay out, and `make_poster.py` refuses to build if one is added; the drawings are original SVGs; the PDF is one 297 × 420 mm page, with a 300 DPI PNG and a `layout-review.json`.
- **Print:** matte or uncoated A3 stock. The 2026‑10‑06 print was too glossy ([audit note](../reference/2026-10-06-aquarium-poster-reference-verification.md)); confirm a shop with matte A3 before going.
- **Not on it:** the department's constants (not public), anything about the sun or moon (D12: not claimed), and anything from the two papers that could not be read.

### The bundle and the chooser

[![The chooser, a Dream starting straight into one clock, and the settings choice](2026-11-21-tide-harbour-clock/chooser.png)](2026-11-21-tide-harbour-clock/chooser.html)

```mermaid
flowchart TD
    A["TV launcher opens<br/>WF Clocks"] --> B{"clock extra<br/>given?"}
    B -- no --> M["Engine level menu<br/>from the MENU chunk"]
    M --> L
    B -- yes --> L["Play that clock<br/>level index from ClockChoice"]
    S["Screensaver starts<br/>(DreamService)"] --> C{"Saved choice"}
    C -- "a clock id" --> L
    C -- "Random" --> R["Pick one, once"] --> L
    L --> Q["Back or Dream ends"]
    Q -- "launcher" --> A
```

```mermaid
sequenceDiagram
    participant U as Person or coordinator
    participant A as ClocksActivity
    participant D as ClocksDreamService
    participant P as TankPlayer / dream_host
    participant E as Engine
    U->>A: start, no clock extra
    A->>P: start(-1)
    P->>E: no positional level, run the menu
    E-->>U: WF Clocks, Choose a clock
    U->>E: OK on Tide Harbour
    Note over E: the engine plays level 1
    U->>A: start --es clock tide_harbour
    A->>P: start(1)
    P->>E: positional level 1, no menu
    D->>D: ClockChoice.chooseForDream()
    D->>P: start(index)
    P->>E: positional level, no menu
```

What changes, file by file:

- `wflevels/clocks-menu.manifest`: `title WF Clocks`, `prompt Choose a clock`, one `level` line per clock.
- `scripts/pack-clocks-bundle.py`: generalises `pack-minute-machine-bundle.py`. It reads the manifest, calls `cdpack --manifest`, and links the result as `android/screensaver/src/clocks/assets/cd.iff`.
- `ClockChoice.java` (like `TankChoice`: `IDS`, `LABELS`, saved choice, `chooseForDream`), `ClockLaunch.java`, `ClocksActivity.java` (reads the `clock` extra), `ClocksDreamService.java`, `ClocksSettingsProvider.java` with a `clock:` setting beside the orientation.
- `dream_host.cc`: `nativeRun` accepts **-1 for "show the menu"**, by leaving out the positional argument, and the upper bound becomes the bundle's length. A test pins the host's argument list, as `tests/test_dream_host_vram.py` already does.
- `build.gradle.kts`: flavor `clocks`; the `minutemachine` flavor, its three `MinuteMachine*.java` classes and its source set are removed, and the manifest, strings, icons and banner are kept under the new name.
- `scripts/gen-screensaver-android-icons.py` and the Taskfile follow.

### Settings objects

Will, 2026‑11‑21: "make sure level has a settings object (same for all clocks---audit)". Every clock level carries one settings object, built the way the Planted Tank, Jellyfish, Reef and Sea Stars levels build theirs ([Sea Stars settings plan](2026-11-20-sea-stars-settings.md), [settings.inc](../../wfsource/source/oas/settings.inc)):

1. **The type.** `wfsource/source/oas/<clock>settings.oas` does `@include settings.inc` and declares fields as `SHOW_AS_…|SHOW_AS_LIVE`; the `.mas` rules generate the `.oad` and `.ht`. A field marked live is one the engine re-reads after the level loads, and that is what makes `levcomp` list the object as editable.
2. **The instance.** The level places one object of that type with no model and no mass. Minute Machine is built through Blender, whose exporter already supports an object that carries `wf_schema_path` ([export_level.py](../../wftools/wf_blender/export_level.py)); Phase 2b confirms a no-model empty works.
3. **The reader.** The director reads each field with `property@ ( actor field -- value valid )`, using the settings actor's index and the field indices written into the script at export time. Nothing scans for the type at run time.
4. **The forms.** The TV form (hold OK) is generated from the `.oad`. The phone's Dream form comes from `scripts/gen-settings-capabilities.py`, which turns the `.oad` into a capabilities asset; the Dream's shared `LevelSettings` saves what the person changed and sends it as launch overrides, which the engine applies when the level loads. The `clocks` app serves the playing clock's fields through one provider, so no clock needs its own.
5. **The Dream variant** keeps the object, its Editable Objects entry and its `OAD ` chunk.
6. **The test** sets every live field, steps the director and checks the pose, as the project rule for live fields requires.

**Audit,** 2026‑11‑21, by `scripts/audit-clock-settings.py` against that list:

| Clock | Type | Live fields | Placed | Read by the director | Phone form | Test | Finding |
|---|---|---|---|---|---|---|---|
| Minute Machine | none | none | none | no `property@` | orientation only | none | **Gap.** Its plan's D10 chose "no settings object" and left one as a later item; that deferral is withdrawn |
| Tide Harbour | none | none | none | none | none | none | **Gap, by design:** not built yet; Phase 2 must build it |
| Sea Stars, for comparison | yes | yes | yes | yes | yes | yes | The reference implementation |

**Common base.** Fields every clock shares go in one include, `wfsource/source/oas/clocksettings.inc`, a `Clock` property sheet that each clock's `.oas` includes after `settings.inc`; adding a field to `settings.inc` itself would change the struct of every settings type, so it is not touched. Each clock's own fields follow in their own sheet. What goes in each is [Q9](#open).

**What changes.** Phase 2 builds Tide Harbour's object with the level; Phase 2b retrofits Minute Machine's; Phase 3 generalises the Dream's `LevelSettings` from its Sea Stars constants to a factory by clock id (its own comment says "not specific to any level") and serves the playing clock's fields; and the audit becomes part of verification so a third clock cannot ship without one.


### Shared code

`channels.py`, `forth.py`, the Blender part helpers and the check scripts in `wflevels/minute_machine/` are mostly not about Minute Machine. They are hoisted into `wflevels/clock_common/` in Phase 2, and Minute Machine is rebuilt from them with its tests unchanged, so a third clock starts from a library, not a copy.

### Engine changes needing permission

| # | Change | Why | Cost |
|---|---|---|---|
| **E1** | Two more system mailboxes: **calendar day** (whole days since 2000‑01‑01, device local) and **UTC offset** (minutes). Latched once a frame with the clock, like `WALL_HOUR`. `WF_WALL_CLOCK` learns a date (`2026-11-21T10:08:22@0`) | The tide and the sunrise change by the day. Without a date there is no tide | Small: Minute Machine's own change, in the same files (`mailbox.inc`, `level.cc`, `wallclock.hp`), and its test file |

E1 is the only engine change, and it is **approved** (Will, 2026‑11‑21: "approval to add date to engine"). Runtime light control (once called E2) is out of this plan and tracked in `TODO.md`.

### State of a clock level

```mermaid
stateDiagram-v2
    [*] --> Menu: launcher, no clock
    [*] --> Playing: clock extra or Dream
    Menu --> Playing: OK on a clock
    Playing --> Menu: Back (launcher only)
    Playing --> [*]: Dream ends
    Menu --> [*]: Back
```

## Phases

| Phase | Work | Tier | Gate |
|---|---|---|---|
| **0 Spikes and research** | (a) 36 plain bars plus 100 boxes on a placeholder level, on cast1: FPS and banding. (b) The look of the day with no light control: a sliding sky, glow actors and keyed looks, judged on the TV at the six moments. ~~(c) The tide: find the Hydrographic Department's constants for a Chao Phraya station, or record that none are public; check the arithmetic against their table.~~ Done 2026‑11‑21: no public constants, but the department's published highs and lows were fitted and validated; [record below](#phase-0-record-the-tide). ~~(d) Sunrise and sunset by day of year against NOAA~~ Dropped by D12: a formula, checked in Phase 2, in place of research | T4 | Answers D5, D7 and the water risk; the plan is revised with the results |
| ~~**1 Engine E1**~~ | ~~Mailboxes, override, tests~~ Done 2026‑11‑21; [record below](#phase-1-record-e1-built) | T4 | ~~`task test-wall-clock` passes with a date; Minute Machine unaffected~~ |
| **2 Tide Harbour level** | `clock_common` hoisted; `wflevels/tide_harbour/` with `timeline.py`, `channels.py`, `parts.py`, Blender build (the dial's Thai numerals are drawn from a Thai font inside the Blender container, so Phase 2 first checks that a Thai font is in the image and adds one to the Dockerfile if not), `-standalone.iff`; **the settings object (D13)**; director VM test; engine comparison | T3 | Director matches the model in the VM and the engine, as Minute Machine's did |
| **2b Minute Machine settings object** | The retrofit the audit found: `minutemachinesettings.oas` including `clocksettings.inc`, one object placed in the Blender-built level, the director reading it with `property@`, the capabilities asset, and `tests/test_minute_machine_settings.py` | T3 | `scripts/audit-clock-settings.py --strict` passes for Minute Machine; its timeline and director tests are unchanged |
| **3 Bundle and chooser** | Manifest, pack script, `LevelSettings` made a factory by clock id and one provider serving the playing clock's fields, `Clock*` classes, host change, flavor `clocks`, `minutemachine` flavor removed | T3 | Desktop and cast1: no argument shows the menu; a named clock skips it; the Dream never shows it |
| **4 cast1** | Install, FPS gate, 10-minute Dream run, six moments checked on the TV, tide gauge checked against the model | T3 | D7 gate, and the moments match the mockups |
| **5 Docs** | `android/screensaver/README.md`, `docs/level-building.md` note, `docs/forth-math-words.md` unaffected | T2 | `task md` renders |
| **P The poster** | The [research document](../reference/chao-phraya-tide-research.md) is written. `docs/reference/chao-phraya-tide-poster/`: `make_poster.py`, `export_poster.py`, original SVG panels, `layout-review.json`, the PDF and a 300 DPI PNG; `tests/test_poster_chao_phraya_tide.py`. **Status: the seahorse poster's generator, exporter and test were read and the layout is mocked up; not yet built.** It needs only Phase 0(c), so it can be built at any time, including before the level exists; panel 6 (the harbour) is redrawn from the finished scene | T3 | PDF is one 297 × 420 mm page; the build refuses an unconfirmed claim; a person has read the printed-size proof |

### Phase 0 record: the tide

Done 2026‑11‑21. Tooling in `wflevels/tide_harbour/tide_fit/`; the full account is the [research document](../reference/chao-phraya-tide-research.md). The three runs below are the evidence.

1. `python3 -I wflevels/tide_harbour/tide_fit/check_time_zone.py`: which clock the department's table uses.

    ```
    Ko Lak: 6562 observed hourly samples in 2025 (GMT), 736 table events for 2026
      table minus GMT =  +7.0 h: median mismatch   11.0 min
      table minus GMT =  +6.5 h: median mismatch   22.0 min
      table minus GMT =  +7.5 h: median mismatch   40.0 min
      table minus GMT =  +0.0 h: median mismatch  308.5 min   (the table is not in GMT)
    RESULT: the table's times are Thai local time (UTC+7)
    ```

    **PASS.**

2. `python3 -I wflevels/tide_harbour/tide_fit/make_constants.py --n 64`: the fit, scored on the year it never saw, both ways.

    ```
    events: 2026 1225, 2027 1222; basis 171 constituents; keeping 64
    fitted on 2026, scored on 2027 (unseen): median 4.5 cm, 90th 11.3, max 22.6  (1222 events)
    fitted on 2027, scored on 2026 (unseen): median 4.1 cm, 90th 10.6, max 21.5  (1225 events)
    shipped constants (both years, 64 constituents), in sample: median 5.2 cm, 90th 11.4, max 19.8
    wrote ../tide_constants.json
    ```

    **PASS.** The first fit that tried (22 constituents) gave a median of 16 cm and was rejected; the Doodson-number basis brought it to 7 cm and the shallow-water compound tides to 3 to 4 cm. The error was the same in and out of sample at every step, which is what showed the model was too small and not overfitted.

3. `python3 -m pytest -q tests/test_tide_constants.py`:

    ```
    .....                                                                    [100%]
    5 passed in 0.25s
    ```

    **PASS.** Mutation check: reading the table as GMT (7 h off) gives a 125.5 cm median and fails; a K1 phase moved by a quarter turn gives 40.1 cm and fails; halving M2 gives 11.9 cm and fails; as shipped, 4.3 cm.

### Audit record: settings objects

Run 2026‑11‑21. `python3 scripts/audit-clock-settings.py`:

    ```
    clock            type     fields   level    director phone    test     settings object
    minute_machine   MISSING  MISSING  MISSING  MISSING  MISSING  MISSING  6 of 6 missing
    tide_harbour     MISSING  MISSING  MISSING  MISSING  MISSING  MISSING  6 of 6 missing
    2 clocks audited, 2 without a complete settings object
    ```

    **Finding: neither clock has a settings object.** `python3 -m pytest -q tests/test_audit_clock_settings.py`:

    ```
    ........                                                                 [100%]
    8 passed in 0.15s
    ```

    **PASS.** The audit's own test: a fake clock with all six parts passes; removing the type, the capabilities asset or the test flips exactly that check; a level that neither places nor reads the object fails two; a type with no live field fails `fields`.

### Phase 1 record: E1 built

Built 2026‑11‑21. `WALL_DAY` is mailbox 1925 (whole calendar days since 2000‑01‑01 in the clock's own time zone, so 2026‑11‑21 is 9821), `WALL_UTC_OFFSET` is 1926 (minutes; Bangkok is 420), and `GLOBAL_SYSTEM_MAX` is 1927. `WF_WALL_CLOCK` takes `[YYYY-MM-DDT]HH:MM:SS[.mmm][+HH:MM|-HH:MM|Z][@rate]`; the time-only form is unchanged. All five mailboxes are latched from one instant per frame. The scripts' `INDEXOF_WALL_DAY` and `INDEXOF_WALL_UTC_OFFSET` come from `mailbox.inc` with no further change. Files: `wallclock.hp`, `mailbox.inc`, `level.hp`, `level.cc`, `tests/wall_clock_test.cpp`, `tests/test_wall_clock.py`, `tests/test_mailbox_global_bounds.py`, `docs/command-line-switches.md`.

1. `task test-wall-clock` (pure C++, no engine; day numbers checked against an independent count, a leap day, the years 2000 and 2100, bad dates and offsets, midnight and a leap-day rollover stepped at exact instants):

    ```
    wall_clock_test: OK
    ```

    **PASS.**

2. The container Debug engine (`scripts/build-wf-game-container.sh --dev`, 70 of 70 linked), then `tests/test_wall_clock.py` and `tests/test_mailbox_global_bounds.py` under `xvfb-run`:

    ```
    tests/test_wall_clock.py::test_frozen_override_reads_back_exactly PASSED [ 11%]
    tests/test_wall_clock.py::test_fast_clock_crosses_a_minute_an_hour_and_midnight PASSED [ 22%]
    tests/test_wall_clock.py::test_without_an_override_it_is_the_device_time PASSED [ 33%]
    tests/test_wall_clock.py::test_a_dated_override_reads_back_the_day_and_the_offset PASSED [ 44%]
    tests/test_wall_clock.py::test_the_day_advances_at_midnight PASSED       [ 55%]
    tests/test_wall_clock.py::test_without_an_override_the_day_and_offset_are_the_devices PASSED [ 66%]
    tests/test_wall_clock.py::test_a_malformed_override_stops_the_engine_at_startup PASSED [ 77%]
    tests/test_mailbox_global_bounds.py::test_global_user_max_is_writable PASSED [ 88%]
    tests/test_mailbox_global_bounds.py::test_global_user_max_minus_one_is_writable PASSED [100%]
    ============================== 9 passed in 16.51s ==============================
    ```

    **PASS.** The three time-of-day tests Minute Machine already had still pass, so its clock is unaffected.

```mermaid
flowchart LR
    P0["Phase 0<br/>spikes"] --> P1["Phase 1<br/>E1"]
    P0 --> P2
    P0 --> PP["Phase P<br/>the poster"]
    P1 --> P2["Phase 2<br/>the level"]
    P1 --> P2b["Phase 2b<br/>Minute Machine settings"]
    P2b --> P3
    P2 --> P3["Phase 3<br/>bundle and chooser"]
    P2 --> P4
    P3 --> P4["Phase 4<br/>cast1"]
    P4 --> P5["Phase 5<br/>docs"]
```

## New and changed files

| File | Change |
|---|---|
| `wflevels/clock_common/` | New: the generic parts of `channels.py`, `forth.py` and helpers, moved from `wflevels/minute_machine/` |
| `wflevels/tide_harbour/` | New: `timeline.py`, `parts.py`, `forth.py`, `blender_create_tide_harbour.py`, `build.sh`, `actor-map.json`, `tide_harbour.lev`, `tide_harbour-standalone.iff.txt`, `tide_constants.json` (done: with its source and the hashes of the tables it was fitted to) |
| `wflevels/tide_harbour/tide_fit/` | Done: `fetch_sources.sh` (one request per file, a pause between), `parse_hd.py`, `constituents.py`, `make_constants.py`, `check_time_zone.py` |
| `tests/test_tide_constants.py` | Done: pins the constants to eight days copied by hand from the printed table; mutation-checked (a 7 h time-zone slip, a wrong K1 phase and a halved M2 each fail it) |
| `docs/reference/chao-phraya-tide-research.md` | Done: sources, calculation, accuracy, and what was not found |
| `docs/reference/chao-phraya-tide-poster/`, `tests/test_poster_chao_phraya_tide.py` | New (Phase P) |
| `wfsource/source/oas/clocksettings.inc`, `minutemachinesettings.oas`, `tideharboursettings.oas` (+ generated `.oad`, `.ht`) | New: the common `Clock` sheet and one settings type per clock (Q9) |
| `scripts/audit-clock-settings.py`, `tests/test_audit_clock_settings.py` | Done: the audit, and its own test (a fake tree with all six pieces passes; removing each flips exactly its check) |
| `tests/test_minute_machine_settings.py`, `tests/test_tide_harbour_settings.py`, `android/screensaver/src/clocks/assets/<clock>-settings.json` | New: per-clock live-field tests and the generated capabilities assets |
| `wflevels/clocks-menu.manifest` | New |
| `scripts/pack-clocks-bundle.py`, `scripts/check-tide-harbour.py` | New |
| `android/screensaver/src/main/java/org/worldfoundry/screensaver/Clock*.java`, `ClocksActivity`, `ClocksDreamService`, `ClocksSettingsProvider` | New; the three `MinuteMachine*.java` classes removed |
| `android/screensaver/src/main/cpp/dream_host.cc`, `tests/test_dream_host_vram.py` | Menu request (-1), bundle bound |
| `android/screensaver/build.gradle.kts`, `src/clocks/`, `src/minutemachine/` (removed) | Flavor `clocks` |
| `mailbox.inc`, `level.cc`, `level.hp`, `wallclock.hp`, `tests/wall_clock_test.cpp` | E1; `docs/command-line-switches.md` for the date override |
| `Taskfile.yml` | `tide-harbour-level`, `clocks-bundle`, `build-clocks-apk`, `test-tide-harbour` |
| `docs/plans/2026-11-21-tide-harbour-clock/` | These mockups and `build_mockups.py` |

## Out of scope

- The other 48 ideas. The bundle makes each one a level and a manifest line; which comes next is Will's call.
- Runtime control of lights (a script-writable light colour, and the clear colour): its own engine feature, in `TODO.md`. This plan works without it.
- The moon's phase, spring and neap tides as a display, weather, sound, other harbours.
- Thai dial numerals (D8), a painterly texture pass (D9), a runtime settings screen beyond the clock choice.
- Any claim that the on-screen tide is a navigation-grade prediction. It is a picture of the tide, to the accuracy Phase 0 measures and prints.

## Verification

These steps are the contract. Each is run when its phase lands, with the raw output recorded under it.

1. `task test-tide-harbour`: the timeline is a pure function of date and time; the tide sum matches the department's table to the error Phase 0 recorded; sunrise and sunset match the checked figures; the director in the real zForth VM matches `timeline.py` for every actor at 125 frames.
2. `task tide-harbour-level`: the Blender container builds `tide_harbour-standalone.iff`; the level has at most 150 animated actors; its signed-volume winding test passes.
3. `python3 scripts/check-tide-harbour.py --compare`: the real engine, set to eight chosen dates and times with `WF_WALL_CLOCK`, agrees with the model on every actor (position, rotation, scale).
4. `task clocks-bundle`, then `cdpack --list wflevels/clocks-screensaver-cd.iff`: two levels in the stated order and a `MENU` chunk.
5. Desktop engine in the container, three runs: no level argument shows the menu (debug-bridge screenshot); `1` plays Tide Harbour with no menu; `0` plays Minute Machine with no menu.
6. `task build-clocks-apk`, then on cast1: `am start … --es clock tide_harbour` shows no menu; the Dream with the saved choice `clock:minute_machine` plays Minute Machine; Random picks one and keeps it for the whole run.
7. cast1 `profile` workflow, Release: median at least 30 FPS over 120 s, and the count of animated actors printed.
8. Six screenshots from cast1, at the six times the mockups show: each reads the right time from the dial, and the tide gauge agrees with the model.
9. `python3 -m pytest -q tests/test_tide_constants.py` and `python3 -I wflevels/tide_harbour/tide_fit/check_time_zone.py`: the constants reproduce the printed table, and the table's clock is UTC+7. Run 2026‑11‑21; output in the [Phase 0 record](#phase-0-record-the-tide). **PASS.**
10. The Forth `tide-m` against the same table: in the VM and in the engine at eight chosen dates and times, within one centimetre of the Python sum (the float error), and within the fit's own error of the table's printed events.
11. `python3 docs/reference/chao-phraya-tide-poster/make_poster.py`, then `export_poster.py`, then `python3 -m pytest -q tests/test_poster_chao_phraya_tide.py`: the PDF is one 297 × 420 mm page, every claim has a chip, no unconfirmed claim is present, and `layout-review.json` reports no overflow. A person reads the printed-size proof.
12. `python3 scripts/audit-clock-settings.py --strict`: every clock in the bundle has all six parts of a settings object, and `python3 -m pytest -q tests/test_audit_clock_settings.py` shows the audit itself can pass and can fail for each part. The test run is in the [audit record](#audit-record-settings-objects); the strict run waits for Phases 2 and 2b.
13. `python3 -m pytest -q tests/test_minute_machine_settings.py tests/test_tide_harbour_settings.py`: each live field is set, the director stepped, and the pose checked, for every field of both clocks.

## Housekeeping done with this plan

- A `TODO.md` entry for each of the two jobs, ranked.
- A row in the [plan index](README.md).
- The mockups are schematics of the design, not game assets. Their tide is now the **real fitted tide** for the date, drawn at an exaggerated scale; the water bars are the technique, flat. The poster mockup's harbour panel is a placeholder.
