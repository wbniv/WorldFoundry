# Investigation: Blender Game Engine removal — history, gap, and World Foundry's fit

**Date:** 2026-04-29
**Status:** Research + opinion. Not a commitment to any specific workstream — more a "huh, is this interesting?" evaluation.
**Related:** `docs/investigations/2026-04-28-engine-capabilities-survey.md`, `docs/investigations/2026-04-28-level-construction-tooling.md`, `wftools/wf_blender/`

---

## What happened

The Blender Game Engine (BGE) was shipped as part of Blender from roughly 2000 until **Blender 2.80** (released 30 July 2019). The code was removed from the source tree on **16 April 2018** by Dalai Felinto; Ton Roosendaal tagged the commit with the message "Bye bye, you did great!" The removal touched 916 files and eliminated entire subsystems: `source/gameengine/`, `source/blender/editors/space_logic/` (the logic-brick editor), the `blenderplayer` standalone executable, and the `intern/moto` motion library.

The Blender Foundation's stated reasons, summarised from release notes and developer forum posts:

1. **No active maintainers since ~2015.** Bugs accumulated without anyone fixing them. A codebase with no maintainers is worse than no codebase.
2. **Irreconcilable rendering debt.** BGE was stuck on OpenGL 2.1 — no geometry shaders, no tessellation, no PBR, no compute. Blender was migrating toward Vulkan/Metal and a new GPU abstraction layer. Threading the BGE's rendering through the new backend would have been a full engine rewrite, not a port.
3. **Tight coupling to Blender internals.** BGE's Python API reached directly into Blender's data structures. Every internal refactor broke the game engine. The maintenance cost was shared with the whole codebase but the user base was small.
4. **Logic bricks.** The visual node-wiring paradigm (sensors → controllers → actuators) was BGE's signature UX. By 2018 it was universally seen as an inferior alternative to scripting; Blender's own node ecosystems (Geometry Nodes, Shader Nodes) had moved in a completely different direction.
5. **Competitive obsolescence.** Godot 3.0 shipped in January 2018, three months before the BGE removal commit. Unity and Unreal had matured into full production tools. BGE had no credible answer to any of them.

The Foundation explicitly recommended **Godot** as the replacement and said so in the 2.80 release notes.

---

## What filled the gap

| Project | Approach | Status (2026) |
|---|---|---|
| **UPBGE** (Uchronia Project BGE) | Fork of BGE, started Sept 2015, kept alive independently after removal. Now runs on Blender 3.x+ codebase and uses EEVEE as renderer. | Actively maintained, small community. |
| **Armory3D** | Blender add-on that compiles a scene to a Haxe/Kha game; targets web, desktop, mobile. Full game logic inside Blender. | Active development. Interesting but niche. |
| **Godot** (official rec) | Separate application; glTF as the exchange format. Excellent physics, scripting (GDScript/C#), full engine. | Dominant open-source choice. |
| **Export to Unity/Unreal** | FBX/glTF export, then do game logic elsewhere. | Mainstream professional workflow. |

UPBGE is the most direct BGE successor: same concept (game logic lives inside Blender's process, Python scripts control objects, you press Play inside the editor). But it is a fork by volunteers, not a Blender Foundation product, and it carries the same architectural baggage it was born from.

---

## What BGE actually was

BGE was an **embedded real-time interactive layer inside Blender**. Not a separate engine — the game ran inside the Blender process. The workflow was:

1. Model and rig inside Blender as normal.
2. Attach logic bricks (or Python scripts) to objects.
3. Press **P** (Play) in the viewport.
4. Blender's rendering loop switched to game mode: physics ticked, scripts ran, player input was polled.
5. Export to a standalone `.blend` + blenderplayer for distribution.

The appeal was frictionless iteration: the asset you're looking at in the viewport *is* the game object. No separate import step, no coordinate-system mismatch, no separate tool to launch.

The cost was everything listed above. And "runs inside Blender" means your game engine is forever coupled to one application's release cycle and internal architecture.

---

## Could World Foundry fill this gap?

The honest answer is: **not today, but the pieces are more aligned than you'd expect**.

### What WF already has that BGE didn't

| Capability | BGE | World Foundry |
|---|---|---|
| Decoupled from Blender internals | No — tightly coupled | Yes — Blender is just an export tool |
| Cross-platform (desktop/mobile/console) | Weak (blenderplayer, limited platforms) | Yes — existing Android port, console-era roots |
| Rendering pipeline independent of Blender | No | Yes — WF has its own renderer |
| Programmable scripting (not logic bricks) | Python only, tightly coupled | zForth (embedded Forth dialect) — minimal, auditable |
| Asset provenance tracking | None | Yes — manifest.json, licence-aware import |
| IFF-based binary format | No | Yes — own level and asset pipeline |

### What WF is missing for a BGE-equivalent position

**1. "Press P" integration.** BGE's killer feature was instant playback inside Blender. WF now has a **"Run in Engine"** button in Properties > Scene > World Foundry Level (`WF_OT_run_level`): one click exports the scene to `.lev`, builds the binary `.iff` via the Rust chain, and launches `wf_game` as a detached process. Blender stays open and interactive while the game runs. This closes 80% of the "Press P" gap.

**2. Live object manipulation.** BGE let you move objects with the mouse during playback; changes were reflected immediately. WF has no equivalent — you edit in Blender, export, and relaunch. A hot-reload mechanism for level data (without restarting the engine) is the hard part.

**3. Physics parity.** BGE shipped with Bullet physics exposed through logic bricks. WF has Jolt physics. The relevant question is whether physics queries (raycasts, collision callbacks, velocity impulses) are accessible from the scripting layer without touching C++ — if that binding exists, there's no gap.

**4. Scripting ergonomics.** BGE Python was accessible (if fragile). WF supports multiple host languages and adding Python as a scripting target is a TODO, not an architectural challenge — it could be done today if the Blender integration made it worthwhile.

### The actual opportunity

The Blender Foundation's Godot recommendation is the key evidence here. The release notes said: *"We recommend using more powerful, open source alternatives like Godot."* The community's reaction to that sentence tells you exactly what BGE users actually wanted.

They weren't upset that Godot isn't powerful. Godot is excellent. They were upset because **the integration was the product**. BGE users weren't comparing rendering pipelines or physics engines — they were comparing two fundamentally different workflows:

- **BGE workflow:** model → rig → attach script → press P → game runs in the same window → tweak → press P again
- **External engine workflow:** model → export FBX → import in separate app → re-wire all logic from scratch → debug two tools simultaneously → repeat

The Foundation recommended a better engine. Users wanted a unified authoring loop. Those are different things, and the recommendation missed the complaint entirely.

This is what UPBGE, Armory3D, and every BGE replacement attempt has been chasing: not engine capability, but **zero-friction iteration from Blender asset to running game without switching contexts**. UPBGE keeps you in Blender's process entirely. Armory3D compiles from Blender's node graph. Both accept significant technical debt to stay inside the Blender window.

WF's approach is different: Blender as exporter, separate engine process, one-button launch. This is architecturally cleaner — no coupling to Blender internals, no renderer debt, portable to any platform. The cost is that you leave the Blender window to run the game. The "Run in Engine" operator narrows that gap dramatically (one click instead of three terminal commands), but it doesn't eliminate it.

The honest framing of the opportunity:

> **WF offers what BGE promised but couldn't deliver: Blender as a first-class authoring environment for a lightweight, distributable game engine** — without the coupling debt that killed BGE, without the architectural lock-in that limits UPBGE, and with a principled asset pipeline that nothing else in this space has.

The audience is people who care more about the authoring loop than the renderer, who want Blender to be their world editor, and who are willing to press one button (not P, but close enough) to see their level running. That audience exists. The BGE community itself was small — tens of thousands at peak — but the broader "Blender users who want to make games" pool is much larger and still has no clean answer to the workflow question the Godot recommendation didn't actually address.

---

## Income speculation

The BGE-positioning angle is almost certainly a PR/community play rather than direct revenue — but there is no free alternative. Consulting clients, a storefront, education outreach all require sustained work too. And WF is already doing most of the BGE-positioning work (publishing the plugin, building the asset pipeline, writing docs). The "BGE replacement" label isn't a separate workstream; it's a description of what's already happening, aimed at an audience that's already looking for it.

Realistic income paths, roughly in order of probability:

1. **Storefront commission on asset sales.** The licence-aware pipeline is unique. No other Blender game toolchain tracks provenance, enforces policy, or writes `manifest.json`. A marketplace that takes a small cut on royalty-free asset sales is a direct revenue model and WF already has the infrastructure for it.
2. **Studio consulting.** A studio using Blender for asset production that wants a lightweight portable engine without Unity/Unreal overhead is a real client. WF solves that problem today.
3. **Education.** Game dev education is large. Unity and Unreal buy pipeline lock-in with free academic licenses. WF with clean Blender integration and no commercial strings would be attractive to educators — and students become practitioners become potential clients.
4. **Community → reputation → contracts.** The indirect path: public tooling builds reputation, reputation brings inbound interest, interest converts to consulting and custom work.

## Recommendations / next steps if pursuing this

These are speculative — not committed work, just logical next steps if this direction is interesting:

1. ~~**Add a "Run in WF" Blender operator.**~~ **DONE (2026-04-29).** `WF_OT_run_level` ("Run in Engine") is implemented in `wftools/wf_blender/`. One click in Properties > Scene > World Foundry Level: export → build `.iff` → launch `wf_game` detached. Progress bar advances 1→2→3 in the status bar; Blender stays open. See `docs/plans/2026-04-29-blender-run-operator.md`.

   The remaining 20% — **live object manipulation / hot-reload** — requires engine-side IFF watching and a reload path so changes propagate without restarting. This is a wanted workstream but not ready to plan yet.

2. **Publish the Blender plugin as a Blender Extension** (the packaging work is planned). UPBGE requires a special Blender build; WF works with stock Blender 4.2+. That's a genuine differentiator.

3. **Write a "getting started" scene.** A minimal `.blend` + `licence_policy.toml` + `wf_game` binary that produces a playable result in under five minutes. BGE's tutorials were the main on-ramp for its community.

4. **Position the asset browser as a differentiator.** No other Blender-adjacent game engine has a licence-aware, provenance-tracking asset pipeline. Godot has an asset library with no licence policy enforcement and no provenance records. This is WF's unique capability and should be front and centre in any community positioning.

---

## Bottom line

BGE was removed because it was technically insolvent — stuck on a deprecated rendering API with no maintainers and mounting coupling debt. Godot filled the general-purpose void. UPBGE is BGE on life support. Nothing in the current open-source landscape fills the specific niche of "Blender-native authoring for a lightweight, distributable game engine with a principled asset pipeline."

World Foundry is not trying to be BGE. But it shares BGE's target audience (people who want to make games *from inside Blender* without switching to a production engine) and solves several of BGE's structural problems by design. Whether to actively pursue that positioning is a product question, not a technical one.

The pieces are there. Someone should press P.

---

## Addendum: the drama

<small>

**[Ton Roosendaal](https://en.wikipedia.org/wiki/Ton_Roosendaal) said "Naaahhh."** At the [Blender Conference in October 2017](https://www.youtube.com/watch?v=ZaWqBmgSpLs&t=1600) — six months before the removal commit — someone asked Ton directly whether the BGE was going to be axed. His response, on camera at ~26:40: *"Remove the Game Engine? I didn't say that? Really? **Naaahhh.**"* A [BlenderArtists thread](https://blenderartists.org/t/ton-remove-the-game-engine-naahhhh/698016) was immediately created with that as the title. The community breathed a collective sigh of relief. Then in April 2018 the engine was gone. Whether Ton genuinely changed his mind during Code Quest or the community read more into "Naaahhh" than he intended has never been clarified.

**The man who deleted the engine had co-written the book on it.** [Dalai Felinto](https://projects.blender.org/blender/blender/commit/159806140fd33e6ddab951c0f6f180cfbf927d38), who committed the 916-file deletion on April 16 2018, is co-author (with Mike Pan) of *Game Development with Blender*, published by Cengage in 2013 — a comprehensive guide to making games with exactly the engine he just deleted. After the removal, [the book was quietly open-sourced on GitHub](https://github.com/mikepan/GameEngineBook). The community noticed.

**The promised replacement quietly died.** Six weeks after the removal, Ton [posted to bf-committers](https://lists.blender.org/pipermail/bf-committers/2018-May/049438.html) announcing Code Quest funds reserved for an "Interactive Mode" — physics running live in the viewport, nodal logic, Godot/Armory3D integration. [Blender's official Twitter](https://x.com/Blender/status/1001110824012967936) named developer **Benoît Bolsee** as lead, on a part-time grant (~1.5 days/week for a year). Bolsee created an `interactive_physics` branch in October 2018, visited the Blender Institute, wrote design docs. Then: nothing. Blender 2.80 shipped July 2019 with no Interactive Mode. No official cancellation was ever announced. By 2020 the community [reported it as "indefinitely on standby."](https://devtalk.blender.org/t/blender-interactive-mode/224/26) This was the second betrayal — and in some ways worse than the first, because the removal was at least honest.

**Dalai told users to move on.** On [task T71930](https://developer.blender.org/T71930) ("Blender Game Engine missing in 2.80+"), Felinto's response to the angry pile-on was terse and final: *"2.79 will be available forever"* and *"The BGE as it is won't come back to 2.80 though."* No "we might reconsider," no roadmap for an alternative. Use 2.79, UPBGE exists, goodbye.

**The Godot recommendation missed the point.** The 2.80 release notes said: *"We recommend using more powerful, open source alternatives like Godot."* The community's objection wasn't that Godot was bad — it was that the *integration* was the entire value proposition. BGE users weren't comparing rendering pipelines; they were comparing "model and test in one window with Python scripting, export to standalone" against "export FBX, re-wire all logic in a separate app, debug two tools at once." Nobody at the Foundation seemed to register that distinction. [(GameFromScratch coverage)](https://gamefromscratch.com/blender-game-engine-in-blender-2-8-life-after-death/)

**[Tristan Porteries](https://github.com/UPBGE/upbge) and UPBGE were perversely freed by the removal.** Porteries had started the fork in September 2015 — three years before removal — precisely because [BGE patches weren't being reviewed upstream](https://upbge.org/docs/latest/manual/manual/introduction/briefing.html). Until the removal they held back aggressive changes hoping for an eventual upstream merge. Once the axe fell, that constraint vanished: EEVEE rendering, physics upgrades, all the things they'd avoided for compatibility. The fork the Foundation never supported was accidentally unleashed. Meanwhile **Mitchell Stokes (Moguri)**, one of the last active BGE maintainers, had quietly faded out by 2015; **Sybren Stüvel (dr.sybren)** [explicitly resigned as BGE patch reviewer](https://developer.blender.org/T54630) in April 2017 with "Resigning as reviewer, as I don't have time for BGE work any more." The maintainer bench was already empty before the axe fell.

**The forum grief was real.** BlenderArtists spawned ["BGE is dead. And the slow death of blender."](https://blenderartists.org/t/bge-is-dead-and-the-slow-death-of-blender/1102916) The question ["What's happening to this forum group now that the BGE is out of Blender?"](https://blenderartists.org/t/whats-happening-to-this-forum-group-now-that-the-bge-is-out-of-blender/1109459) drew **292 replies** — nearly 300 people debating the fate of a *subforum*. As late as March 2021, **Jorge Bernal (lordloki)** — an UPBGE developer — was still on [devtalk trying to get acknowledgment](https://devtalk.blender.org/t/ton-roosendaal-blender-2-8-realtime-and-interactive-3d-blender-2-9-blender-game-engine/18073) of Interactive Mode's status: *"I believe that although it has never been made totally clear a game engine will never be included in Blender again."* No Blender Foundation developer engaged with that thread.

**No petition.** The energy dissipated into UPBGE rather than lobbying. The only related petition found was for restoring Blender Internal (the renderer also removed in 2.80) — it got six signatures and closed. Nobody fought for a reversal. They just forked and moved on.

</small>
