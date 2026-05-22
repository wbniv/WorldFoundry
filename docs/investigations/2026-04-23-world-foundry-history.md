# World Foundry / Project Velocity — Public History

An aggregation of externally available references to the World Foundry GDK and its predecessor game projects.

---

## Studio Background

**Cave Logic Studios, Ltd.** was co-founded by Kevin Seghetti and Will Norris in September 1994.  The stated motivation (per the GDRI interview) was to negotiate shared ownership of engine and library code rather than assigning all IP to publishers — unusual for the era.

Before Cave Logic, both worked together on the SNES port of *Ballz* (1994, port from Genesis; notable for "re-bugging" the code to preserve the Genesis version's animation quirks intentionally).

**Recombinant Limited** was the renamed successor to Cave Logic, operational from around October 1996.  Kevin Seghetti's resume lists his role there as Senior Software Engineer (Oct 1996 – Jul 1998), responsible for the 3D engine, physics/collision, and artist/designer tooling.  Cave Logic's codebase and tools were licensed to Recombinant at the transition.

---

## Project Velocity (1994–~1997)

- **Developer:** Cave Logic Studios / PF Magic (collaboration)
- **Intended platforms:** PlayStation, Sega Saturn
- **Publisher:** Virgin Games (reported as potential publisher, c. 1996–97)
- **Status:** Cancelled, never officially announced
- **Genre:** Sci-fi action / 3D

After *Ballz*, Cave Logic partnered with PF Magic on a 3D action game codenamed *Velocity*.  Kevin Seghetti's GDRI interview: *"For many reasons, that project took several years and was eventually canceled."*

Velocity was the first project to use what became the World Foundry engine — a textured-polygon streaming renderer targeting the PS1's 33 MHz R3000.  The engine was specifically designed so that level geometry could be streamed off a single CD-ROM file as the player moved through the world, enabling apparent world sizes larger than could fit in RAM.

The Sega Retro wiki has a stub entry for [Velocity (Saturn)](https://segaretro.org/Velocity_(Saturn)).

---

## Cyberthug (1996–~1997)

- **Developer:** Recombinant Limited (Cave Logic's successor)
- **Publisher:** MGM Interactive
- **Platform:** PlayStation
- **Status:** Cancelled when MGM Interactive shut down
- **Engine:** World Foundry (same codebase as Velocity)

After Velocity's cancellation, Recombinant began *Cyberthug* for MGM Interactive using the same engine.  MGM Interactive was dissolved by MGM a few months into the project.  A tie-in promotional comic book was published (MGM Cyberthug #1, confirmed collectible); EGM September 1996 carried coverage.

References: [Unseen64 — Cyber Thug](https://www.unseen64.net/2008/05/05/cyber-thug-psx-cancelled/), [Unreleased Games wiki](https://unreleasedgames.miraheze.org/wiki/Cyber_Thug), [Gameluv writeup](https://gameluv.com/luv/6456/mgms-cyberthug-another-game-that-never-was/).

---

## World Foundry GDK — Open Source Release

Following the collapse of Cyberthug and Kevin Seghetti's transition out of game development (he moved into embedded/HVAC firmware from ~1998 onward), the engine was GPL-released and posted to SourceForge.

| Fact | Value |
|---|---|
| SourceForge registration | 19 November 1999 |
| First commit | February 2000 |
| Last SourceForge update | 9 April 2013 |
| License | GPLv2 |
| Stated LOC | 170,000+ |
| Languages | C++, Perl, Tcl |
| Target platforms | Windows (primary), Linux (partial port) |
| SF maintainers | `kts` (Kevin Seghetti), `wbniv` (Will Norris) |
| SourceForge page | [wf-gdk](https://sourceforge.net/projects/wf-gdk/) |
| OpenHub page | [wf-gdk on OpenHub](https://www.openhub.net/p/wf-gdk) |

The OpenHub COCOMO model estimated ~39 person-years of effort.  The SourceForge page notes "1 download this week" and "Beta" status as of its last update.

Key design properties advertised on the project page and worldfoundry.org wiki:
- CD streaming of large worlds from a single `.iff` file
- Modular scripting via Tcl (level logic without engine code changes)
- Director-style camera model for cutscenes
- Originally designed for PS1 hardware constraints, so runs well on low-end PC hardware
- Content (the single `.iff` game file) can be commercial even under GPL

The worldfoundry.org domain hosted a Foswiki (formerly TWiki) instance.  40 engine screenshots were posted there as documentation.  The site used a self-signed certificate and is not reliably reachable as of 2026.

The Tcl wiki has a short entry: [World Foundry — Tcl wiki](https://wiki.tcl-lang.org/page/World+Foundry), noting the Tcl scripting integration and linking to the official site.  Last edited there 2021-04-07.

---

## Kevin Seghetti — Later Reference to World Foundry

In the Sega-16 interview (March 2013), Seghetti mentioned that he had recently begun "porting [World Foundry] to OpenGL ES 2.0 so it could run on smartphones" — the `2026-googletv` branch in this repo is the current continuation of that effort.

His resume (tenetti.org) describes World Foundry as a "reusable 3D video game engine" with resource streaming, and lists the GPL release.

---

## External References and Coverage

### Primary interviews
- [Interview: Kevin Seghetti — Sega-16 (March 2013)](https://www.sega-16.com/2013/03/interview-kevin-seghetti/) — covers full career from Amiga through World Foundry; most technically detailed
- [Interview: Kevin Seghetti — GDRI (2008-12-11)](http://gdri.smspower.org/wiki/index.php/Interview:Kevin_Seghetti) — original interview; source for Velocity/Cyberthug details (returns 403 directly, mirrored at [Sega Retro](https://segaretro.org/Interview:_Kevin_Seghetti_(2008-12-11)_by_Game_Developer_Research_Institute))

### Cancelled-game databases
- [Velocity [PSX/Saturn — Cancelled] — Unseen64 (2010-11-04)](https://www.unseen64.net/2010/11/04/velocity-psx-saturn-cancelled/) — contributed by "Celine"; includes engine attribution
- [Cyber Thug [PSX — Cancelled] — Unseen64 (2008-05-05)](https://www.unseen64.net/2008/05/05/cyber-thug-psx-cancelled/) — includes proto screenshots and EGM/Console Mania magazine scans
- [Velocity (Saturn) — Sega Retro](https://segaretro.org/Velocity_(Saturn)) — stub wiki entry
- [Cave Logic Studios/Recombinant Limited — GDRI](http://gdri.smspower.org/wiki/index.php/Cave_Logic_Studios/Recombinant_Limited) — studio page (returns 403 directly)

### Project registries
- [World Foundry GDK — SourceForge](https://sourceforge.net/projects/wf-gdk/)
- [World Foundry GDK — OpenHub](https://www.openhub.net/p/wf-gdk)
- [World Foundry — Tcl wiki](https://wiki.tcl-lang.org/page/World+Foundry)

### Developer profile
- [Kevin Seghetti resume](http://tenetti.org/kts/resume.html) — employment dates for Cave Logic and Recombinant confirm timeline

---

## Codebase Reviews

No formal third-party code reviews of World Foundry GDK appear to exist in any indexed source.  The OpenHub project page reports zero user reviews.  The SourceForge page similarly shows no reviews.  The engine predates the era of "Let's examine retro open-source game engines" YouTube/blog content, and its low download count (the SF page shows single-digit weekly downloads even recently) suggests it was not widely adopted or studied by hobbyists.

The only technical commentary comes from Kevin Seghetti himself in the Sega-16 interview, describing it as "a textured polygon engine which runs at decent framerates on a 33Mhz R3000."

---

## Timeline Summary

| Date | Event |
|---|---|
| Sept 1994 | Cave Logic Studios founded by Kevin Seghetti and Will Norris |
| 1994–~1997 | *Velocity* in development (PSX/Saturn, with PF Magic); World Foundry engine begins |
| ~1996 | Cave Logic becomes Recombinant Limited |
| Sept 1996 | EGM covers *Cyberthug* |
| ~1996–1997 | *Cyberthug* in development (PSX, MGM Interactive); cancelled when MGM Interactive folds |
| Jul 1998 | Seghetti leaves Recombinant; moves into firmware/embedded work |
| 19 Nov 1999 | World Foundry GDK registered on SourceForge |
| Feb 2000 | First SourceForge commit |
| 9 Apr 2013 | Last SourceForge activity |
| Mar 2013 | Seghetti mentions OpenGL ES 2.0 smartphone port in Sega-16 interview |
| 2021-04-07 | Last edit to Tcl wiki entry |
