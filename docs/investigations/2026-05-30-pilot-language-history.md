# The PILOT Language — History, Implementations, and Whether Anyone Still Uses It

> **Scope.** This report is about the *historical* **PILOT** programming language — the
> 1960s computer-assisted-instruction (CAI) language — **not** World Foundry's in-engine
> object-script language, which deliberately borrows the name and the design. See
> [Relation to World Foundry's Pilot](#relation-to-world-foundrys-pilot) at the end.
>
> Investigation date: 2026-05-30. Sources are linked inline and collected in
> [References](#references).

---

## 1. What PILOT is

**PILOT** — *Programmed Inquiry, Learning, Or Teaching* — is a small, line-oriented
language for **authoring computer-assisted instruction (CAI)**: drills, quizzes,
branching tutorials, and question-and-answer dialogues. Its intended author was the
*teacher*, not the professional programmer. The entire language is built around one
loop — **emit a prompt → accept a response → match it → branch on the result** — and
makes that loop a four-line idiom.

That match-and-branch step (**answer-judging**) is the defining feature: a built-in
`Match` compares the learner's free text against expected patterns, sets a yes/no flag,
and the following lines act differently on a hit vs. a miss.

---

## 2. History

| When | Event |
|------|-------|
| **1960** | John Amsden Starkweather, a psychology professor at the **University of California, San Francisco (UCSF)** medical center, begins building a system to automate the construction of computer question-and-answer tests. |
| **1962** | Working with the **Dixie Elementary School District** (Marin County), the system runs on an **IBM 1620** under the name **COMPUTEST**. |
| **1965** | After UCSF installs an IBM System/360 Model 50, Starkweather wins a **U.S. Office of Education** grant to build an expanded successor — renamed **PILOT**. |
| **1966 → 1968** | Early PILOT shown in 1966; the near-complete version released in 1968. |
| **1969** | PILOT is released into the **public domain**. |
| **1970s** | PILOT spreads to timesharing terminals and minicomputers. **H. Dean Brown** at the **Stanford Research Institute (SRI)** Education Laboratory popularizes it as a language *for children to program in* — a shift from "teachers author lessons" to "students learn programming." |
| **1973** | Starkweather convenes interested parties to define a machine-independent specification: **PILOT-73**. |
| **late 1970s** | **Western Washington University** extends the language into **Common PILOT**, the basis for most of the 1980s microcomputer dialects. |
| **early 1980s** | The microcomputer boom is PILOT's peak — Apple, Atari, Commodore, CP/M, and Zenith dialects ship into schools and homes; turtle graphics and sound are added. |
| **1987–1991** | Starkweather chairs an **IEEE** working group that produces **IEEE Std 1154-1991, *Standard for the PILOT Language***. |
| **2000** | The effort to maintain a single standard is **abandoned**; the IEEE standard is later **withdrawn**. PILOT recedes to historical, hobbyist, and retrocomputing interest. |

Starkweather's motive was practical: let clinicians and teachers write their own
interactive lessons without learning FORTRAN. PILOT is best read as the lightweight
contemporary of the era's heavier CAI systems — **TUTOR** (the PLATO language), IBM's
**Coursewriter**, **PLANIT** — and a sibling of **Logo** in the "computing for
education" movement. One concrete institutional adopter: the **National Library of
Medicine** used PILOT to disseminate health-sciences instructional material and to
train medical librarians on **MEDLINE**.

---

## 3. Language design

A line of PILOT has, left to right: an optional **label** (`*name`), a **command
letter**, an optional **`Y`/`N`** conditioner, an optional **conditional expression**
in parentheses, a **colon**, and the **operand(s)** (comma-separated):

```
[*label] CMD [Y|N] [(condition)] : operand[,operand...]
```

The `Y`/`N` conditioner is where PILOT's terseness comes from: it gates *any* command on
the last match result. `TY:` types only on a match, `JN:` jumps only on a miss, etc.

### Standard command set

| Cmd | Name | Effect |
|-----|------|--------|
| `T:` | **Type** | Output text (with variable interpolation). |
| `A:` | **Accept** | Read a line of input from the learner. |
| `M:` | **Match** | Compare the accept buffer against a comma-separated pattern list; set the yes/no flag. |
| `Y:` | **Type-yes** | Output text only if the last match succeeded. |
| `N:` | **Type-no** | Output text only if the last match failed. |
| `J:` | **Jump** | Branch to a label. |
| `U:` | **Use** | Call a subroutine. |
| `C:` | **Compute** | Arithmetic / variable assignment. |
| `D:` | **Dimension** | Declare arrays. |
| `E:` | **End** | Return from a subroutine, or end / abort the program. |
| `R:` | **Remark** | Comment. |

Labels are written `*START`. The most recently accepted input lives in a default
*accept buffer*; later dialects add named numeric and string variables.

### Canonical example — a one-question drill

```pilot
T:What is the capital of France?
A:
M:Paris,PARIS,paris
TY:Correct!
TN:No — the capital of France is Paris.
E:
```

Prompt, accept, judge, branch on the judgement, give feedback. Everything else in the
language scales that loop up into multi-screen lessons.

### Turtle graphics and sound (1980s dialects)

The microcomputer dialects bolted on a **turtle-graphics** subsystem (pen, move, turn —
Logo-style) and sound, so the same language could drive illustrated, kid-facing
courseware. This is why Atari PILOT, Vanilla PILOT, and Apple SuperPILOT feel like a CAI
cousin of Logo.

---

## 4. Implementations and dialects

### Historical

| Implementation | Platform | Year | Notes |
|----------------|----------|------|-------|
| **COMPUTEST** | IBM 1620 | 1962 | Starkweather's precursor (with the Dixie Elementary School District). |
| **PILOT** | IBM System/360 | 1966–68 | The original; public domain 1969. |
| **PILOT-73** | machine-independent spec | 1973 | First portability effort. |
| **Core PILOT** | Datapoint 2200 | 1970s | Portable subset. |
| **Common PILOT** | (spec/base) | late 1970s | Western Washington University; basis for the micro dialects. |
| **PETPILOT** | Commodore PET | 1979 | |
| **Nevada PILOT** | CP/M | early 1980s | Based on Common PILOT; widely distributed (Ellis Computing). |
| **Atari PILOT** | Atari 8-bit | 1981 | ROM cartridge; added turtle graphics + sound; derived from Nevada/Common. |
| **Apple PILOT** | Apple II | early 1980s | Written in UCSD Pascal; added arrays + floating point. |
| **Apple SuperPILOT** | Apple II | ~1982 | Full authoring system; added device control (videodisc). |
| **Vanilla PILOT** | Commodore 64 | 1983 | Included turtle graphics. |
| **ZPILOT** | Zenith Z-100 | 1983 | |
| **Super Turtle PILOT** | — | 1987 | Turtle-graphics-focused. |
| **eSTeem PILOT** | Atari ST | 1990 | LaserDisc + CD-ROM control. |
| **PYLON / NYLON** | — | — | Incompatible offshoot variants. |

### Standard

- **[IEEE Std 1154-1991](https://standards.ieee.org/standard/1154-1991.html)** —
  *IEEE Standard for the PILOT Language*. A late, formal codification; the
  standardization effort was abandoned in 2000 and the standard later withdrawn. Its
  existence marks how seriously PILOT was once taken in educational computing.

### Current / still-runnable

- **[Eric S. Raymond's `ieee-pilot`](https://gitlab.com/esr/ieee-pilot)** — a C
  reference implementation of PILOT *as specified by IEEE 1154-1991*. ESR maintained it
  for roughly 15 years; the most recent commits are around **2016 / 2019**, so it is
  effectively dormant but complete and buildable today. This is the closest thing to a
  canonical living implementation.
- **psPILOT** (2018) — a hobbyist PILOT implementation written in **PowerShell**.
- **Retrocomputing / emulation** — the two best-known 8-bit dialects (Apple SuperPILOT,
  Atari PILOT) run under emulators, which is how most people who "use" PILOT now touch
  it. A.P.P.L.E. has even published a retrospective book,
  *[All About Pilot](https://www.callapple.org/books-3/all-about-pilot/)*, collecting
  PILOT articles across retro platforms.

> ⚠ Not the same language: RPI's "[PILOTS](http://wcl.cs.rpi.edu/pilots/)" is an
> unrelated modern declarative language for spatio-temporal data streams — name
> collision only.

---

## 5. Does it have any place in contemporary education?

**As a tool for authoring or delivering lessons: effectively none.** PILOT solved a
1970s–80s problem — let a teacher script an interactive drill on a single-user
micro — that has since been solved repeatedly and far more capably:

- **HyperCard** (1987), then **Authorware / ToolBook**, absorbed CAI authoring.
- The **web** (HTML/JavaScript) and **learning-management systems** (Moodle, Canvas)
  absorbed it next.
- Modern **interactive-content tools** (H5P, Articulate Storyline, Google Forms quizzes)
  are what a teacher reaches for today to build exactly the branching quiz PILOT was
  invented for.

A present-day educator has no practical reason to choose PILOT over those.

**As a teaching *subject*, it keeps a small but genuine niche:**

- **History-of-computing / history-of-edtech** courses cite it as a landmark — one of
  the first languages aimed squarely at non-programmer educators, and an early, legible
  model of answer-judged interaction.
- It's a clean **case study in language minimalism**: a complete, useful language with
  ~10 commands.
- Its answer-judging model is a tidy way to introduce the *ideas* behind today's quiz
  engines and rule-based chatbots — even though nobody implements those in PILOT now.

---

## 6. Does anyone still actually use PILOT — who, and why?

Honestly: **no one uses PILOT for new production courseware.** The people who touch it
today are a few small, well-defined groups, and their reasons are about *the past and
the craft*, not getting CAI work done:

1. **Retrocomputing hobbyists** — running Apple SuperPILOT / Atari PILOT under emulation
   or on original hardware. *Why:* preservation, nostalgia, period-authentic tinkering.
   The 8-bit revival has grown through the 2010s–2020s, and the *All About Pilot*
   anthology is a direct product of that community.
2. **Language preservationists / interpreter authors** — e.g. Eric Raymond's IEEE
   reference implementation, and one-off ports like psPILOT (PowerShell, 2018). *Why:*
   PILOT is small, charming, and fully specified (IEEE 1154 gives a target to hit).
3. **Esoteric / recreational programmers** — who enjoy its terseness as a puzzle.
4. **Educators and historians teaching *about* it** — in computing-history or
   PL-survey contexts. *Why:* it's a compact, important data point in how computers
   entered the classroom.

The one-line answer to "does anyone still use PILOT?": **only enthusiasts,
preservationists, and historians — for love of the artifact, not because it's the right
tool for any current job.** Its *ideas* (answer-judging, branch-on-response dialogue)
are alive and ubiquitous; the *language itself* is a lovingly-kept museum piece.

---

## 7. Legacy and influence

PILOT's lasting contribution is conceptual. It helped establish, for a generation of
educators, that a computer could hold an interactive *dialogue* with a learner; that
**answer-judging** (match the response, branch on it, give targeted feedback) is the
heart of computer tutoring; and that a language narrow enough to learn in an afternoon
could still do real work. Those ideas flow directly into every modern quiz engine,
adaptive-learning tool, and rule-based conversational tutor — none of which are written
in PILOT.

---

## Relation to World Foundry's Pilot

World Foundry has its own in-engine object-script language **also called "Pilot"** (see
[`docs/pilot-language.md`](../pilot-language.md) and the implementation plan
[`docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md`](../plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md)).
It is a deliberate descendant, not a coincidence of names: WF's spec opens by citing
PILOT as "a 1960s line-oriented language" and adopts its exact statement grammar —
`VERB [Y|N] [(guard)] : operand`, `*label` jump targets, `T:`/`A:`/`M:`/`C:`/`J:`/`U:`/
`E:`/`R:` verbs, a persistent match flag, and the same emit→await→classify→branch loop —
then extends it with engine-control verbs (`SP:`, `WM:`, `IN:`, …) and runs it on two
surfaces (in-engine `MailboxHost` and external `BridgeHost`) from one shared interpreter.

Even the historical turtle-graphics lineage shows up: WF's spec **reserves `GR:` (and a
3D turtle vocabulary) for a later phase** — the same `GR:` turtle subsystem that Atari
PILOT, Vanilla PILOT, and Apple SuperPILOT added in the 1980s. So WF's Pilot is best
understood as a modern, game-engine-flavored revival of exactly the language this report
describes.

---

## References

- [PILOT — Wikipedia](https://en.wikipedia.org/wiki/PILOT)
- [John Amsden Starkweather — Wikipedia](https://en.wikipedia.org/wiki/John_Amsden_Starkweather)
- [IEEE Std 1154-1991 — Standard for PILOT](https://standards.ieee.org/standard/1154-1991.html)
- [Eric S. Raymond — `ieee-pilot` reference implementation (GitLab)](https://gitlab.com/esr/ieee-pilot)
- [The PILOT Programming Language on CP/M — techtinkering](https://techtinkering.com/articles/the-pilot-programming-language-on-cpm/)
- ["Pilot Your Atari" — ANTIC / Atari magazines](https://www.atarimagazines.com/v1n1/pilotyouratari.html)
- [Apple PILOT — Centre for Computing History](https://www.computinghistory.org.uk/det/44786/Apple-Pilot/)
- [SuperPILOT — ERIC ED261650](https://eric.ed.gov/?id=ED261650)
- [*All About Pilot* — A.P.P.L.E.](https://www.callapple.org/books-3/all-about-pilot/)
- [Register of the John A. Starkweather Papers, 1965–1985 — Online Archive of California](https://oac.cdlib.org/findaid/ark:/13030/tf2d5nb1xg/entire_text/)
