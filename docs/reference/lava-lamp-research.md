# The lava lamp: physics, wax, history, patents and the level's Forth

**Research for the lava lamp clock's A3 poster, 2026‑11‑26.** Written first, as for the [Tide Harbour poster](chao-phraya-tide-research.md): the poster prints only what this document supports, and [`make_poster.py`](lava-lamp-poster/make_poster.py) refuses a source whose link is not written here. The plan is [Lava lamp](../plans/2026-11-26-lava-lamp.md#the-a3-poster). Every page below was fetched on 2026‑11‑26.

Every claim carries one label:

- **verified**: the source was read, and it says this about the lava lamp or its materials;
- **other source**: read, but about another lamp, and used only as stated;
- **ours**: our level, our model or our design; a measured number names the script that computes it.

What could not be confirmed is listed [at the end](#what-was-not-found-or-was-corrected) and is never printed.

Poster visual review: pending (Will). Until Will approves and this line is changed to say so, `make_poster.py` builds only a marked review draft.

## How it moves

**Verified** ([Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp), section "Operation"): a lamp heats a tall glass bottle holding water and a wax mix. Common wax "has a density much lower than water and floats at any temperature"; carbon tetrachloride, "about 60% denser than water", nonflammable and miscible with wax, was added to raise the wax's density at room temperature. Heated, the wax expands, becomes less dense and rises; as it cools its density increases and it sinks. "A metallic wire coil in the bottle's base breaks the cooled blobs' surface tension, allowing them to merge and repeat the cycle." The underlying fluid mechanics "is a form of Rayleigh–Taylor instability". Agitating a lamp whose wax has melted emulsifies the two fluids into a cloudy mess.

**Verified, primary** ([US 3,387,396](https://patents.google.com/patent/US3387396A/en), [PDF](https://patentimages.storage.googleapis.com/d6/63/51/33f1fdc371eaf6/US3387396.pdf), description and claim 1): the globule's liquid can be "mineral oil, paraffin and a dye" in water, "for example, Ondina 17 with a light paraffin, carbon tetrachloride and a dye or dyes"; a gelling agent such as paraffin wax keeps it solid when cold, and at "say 45 50 C." it "becomes fluent". Claim 1 puts the heater beneath the container and "a surface tension breaker comprising a spiral wire ring … within the container at the base thereof".

**Verified** ([How Products Are Made, "Lava Lamp"](https://www.encyclopedia.com/manufacturing/news-wires-white-papers-and-books/lava-lamp), Encyclopedia.com, the section on use): on first use the lava may not flow or may float to the top; the lamp "should be allowed to heat up for four hours or more" for the lava to become completely molten.

## The wax and the liquid

| Property | Value | Label | Source and locator |
|---|---|---|---|
| Paraffin wax density | around 900 kg/m³ (0.9 g/cm³) | verified | [Wikipedia, "Paraffin wax"](https://en.wikipedia.org/wiki/Paraffin_wax), "Properties" |
| Paraffin melting point | typically 46 to 68 °C | verified | same |
| Volume on heating to the melting point | grows by up to 10 % | verified | [Schimmelpfennig, Weber, Kalb, Feller, Butz, Matthäi, "Volume expansion of paraffins from dip tube measurements"](https://ic.unicamp.br/~stolfi/EXPORT/projects/wikipedia/00-DOCS/Volume_expansion_of_paraffins_from_dip_tube_measur.pdf), Introduction: "the volume of paraffin waxes increases by up to 10 % on heating up to the melting point" |
| Carbon tetrachloride density | 1.5867 g/cm³ (liquid) | verified | [Wikipedia, "Carbon tetrachloride"](https://en.wikipedia.org/wiki/Carbon_tetrachloride), infobox |
| Carbon tetrachloride in US lamps | not used since 1970, banned that year for toxicity | verified | [Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp), "Operation" (citing the US EPA's toxicological review) |
| Today's formula | Haggerty, the US maker, calls it a trade secret | verified | same |
| Mathmos's formula | developed by Craven Walker in the 1960s and improved with his help in the 1990s; still used | verified | [Wikipedia, "Mathmos"](https://en.wikipedia.org/wiki/Mathmos), "Company history" |

The density-against-temperature drawing on the poster is **ours, schematic**: two falling lines that cross. Neither slope is a measurement.

## Patents

Each checked on Google Patents on 2026‑11‑26 (title, inventor or applicant, assignee, dates; the PDF link where Google gives one). The poster prints each number as a link and a QR code to the page below.

| Number | Title (as filed) | Inventor, assignee | Dates (Google Patents) | What it is |
|---|---|---|---|---|
| [GB 703,924](https://patents.google.com/patent/GB703924A/en) | A display device using liquid bubbles in another liquid | Donald Dunnet | filed 1950‑12‑21, published 1954‑02‑10 | Two immiscible liquids, the lower heated by a lamp so it rises in bubbles that cool and return (abstract). The lava lamp's precursor ([Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp), "History") |
| [US 3,387,396](https://patents.google.com/patent/US3387396A/en) | Display devices | David George Smith; Crestworth Ltd | priority 1964‑03‑18, filed 1965‑03‑04, granted 1968‑06‑11 | The lava lamp: wax that flows when heated, a heater below, a spiral wire surface-tension breaker ([PDF](https://patentimages.storage.googleapis.com/d6/63/51/33f1fdc371eaf6/US3387396.pdf)) |
| [US 3,689,139](https://patents.google.com/patent/US3689139A/en) | Optical projector | Alexander Gross and Ilene Astrahan Gross (Google's record spells him "Alexauder") | priority 1968‑10‑03, filed 1969‑09‑22, granted 1972‑09‑05 | A projector whose slide holds immiscible coloured fluids; cites Dunnet ([PDF](https://patentimages.storage.googleapis.com/ac/58/51/c3605f44a879ec/US3689139.pdf)) |
| [US 3,777,379](https://patents.google.com/patent/US3777379A/en) | Aesthetic fluid suspension and its preparation | W. Lewellen | filed 1969‑03‑07, granted 1973‑12‑11 | A contrasting gel held in place inside a gel of high yield value; cites Dunnet ([PDF](https://patentimages.storage.googleapis.com/45/f6/32/71a37b22cf7163/US3777379.pdf)) |
| [US 4,057,921](https://patents.google.com/patent/US4057921A/en) | Decorative device | Derek William Ball | priority 1976‑04‑13, filed 1976‑05‑24, granted 1977‑11‑15 | Flat chambers of coloured immiscible fluids that overlap in moving patterns; cites Dunnet ([PDF](https://patentimages.storage.googleapis.com/4e/60/b6/9e4f9a53d171e3/US4057921.pdf)) |
| [US 5,732,138](https://patents.google.com/patent/US5732138A/en) | Method for seeding a pseudo-random number generator with a cryptographic hash of a digitization of a chaotic system | Landon Curt Noll, Robert G. Mende, Sanjeev Sisodiya; Silicon Graphics Inc | filed 1996‑01‑29, granted 1998‑03‑24 | Lavarand ([PDF](https://patentimages.storage.googleapis.com/6d/9b/ee/d30a9570cd8af3/US5732138.pdf)) |

"Cites Dunnet": GB 703,924's own page lists US 3,387,396, US 3,689,139, US 3,777,379 and US 4,057,921 under "Cited By", each marked as cited by the examiner. The plan's patent table gave US 3,689,139 only its grant date and Gross alone as inventor; both are corrected here.

## History

All **verified**, from the page named in each line.

- **1950.** Donald Dunnet files GB 703,924. Craven Walker later conceives the lava lamp after seeing a home-made egg timer, made from a cocktail shaker, bubbling on a pub stove; Wikipedia names Dunnet's patent as that precursor ([Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp), "History").
- **1959.** Under the pseudonym Michael Keatering, Craven Walker directs *Travelling Light*, "the first naturist film to receive public release in the UK"; shot off Corsica and released in 1960 ([Wikipedia, "Edward Craven Walker"](https://en.wikipedia.org/wiki/Edward_Craven_Walker), "Film work"; [Wikipedia, "Travelling Light (1959 film)"](https://en.wikipedia.org/wiki/Travelling_Light_(1959_film)): a 1959 film, released March 1960). Q7: Will asked for this line.
- **1963.** Crestworth launches the first Astro lava lamp; Mathmos lamps have been made in Poole, Dorset, since 1963 ([Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp)).
- **1965.** Adolph Wertheimer and Hy Spector see the lamp at a German trade show, buy the American rights and start the Lava Manufacturing Corporation in Chicago to sell the Lava Lite Lamp (same page).
- **1968.** US 3,387,396 is granted to Crestworth (Google Patents, above).
- **1970.** Carbon tetrachloride leaves US lamps (above).
- **Late 1970s.** The US rights are sold to Larry Haggerty, whose Lava World International made American lava lamps for over 30 years ([Wikipedia, "Lava lamp"](https://en.wikipedia.org/wiki/Lava_lamp)).
- **1989 and 1992.** Cressida Granger and David Mulley take over Crestworth in 1989 and rename it Mathmos in 1992, after "the seething lake of energy resembling lava beneath city Sogo in the 1962 comic Barbarella". Sales grow "from 10,000 lamps a year in 1989 to 800,000 lamps a year in 1999" ([Wikipedia, "Mathmos"](https://en.wikipedia.org/wiki/Mathmos)).
- **1996.** Silicon Graphics designs Lavarand, a random-number generator seeded from pictures of lava lamps; the patent above is filed that year ([Wikipedia, "Lavarand"](https://en.wikipedia.org/wiki/Lavarand)).
- **2000.** Craven Walker dies on 15 August 2000, aged 82; he remained a consultant at Mathmos until his death, helping to improve the formula ([Wikipedia, "Edward Craven Walker"](https://en.wikipedia.org/wiki/Edward_Craven_Walker)).
- **2017.** Cloudflare launches its own entropy system, a wall of around 100 lava lamps in the lobby of its San Francisco headquarters, inspired by Lavarand ([Wikipedia, "Lavarand"](https://en.wikipedia.org/wiki/Lavarand)); Cloudflare's own account of the wall is dated 6 November 2017 ([Cloudflare blog, "LavaRand in Production"](https://blog.cloudflare.com/lavarand-in-production-the-nitty-gritty-technical-details/)).

## The base

**Other source** ([How Products Are Made, "Lava Lamp"](https://www.encyclopedia.com/manufacturing/news-wires-white-papers-and-books/lava-lamp)): "The original **Century** model … Its gold base is perforated with tiny holes which simulate starlight", with "red or white lava and yellow or blue liquid". That is the American Lava Lite Century, not the British Astro (see the correction below). Our base borrows the idea.

**Ours** (`wflevels/lava_lamp/generate.py`): the base is a 29 × 9 grid of holes; lit holes spell the local time, 24-hour, and every other hole glows faintly. The holes switch once a minute; the wax never knows the time.

## The level's Forth

**Ours.** The director script is written by `wflevels/lava_lamp/forth.py` from `model.py`: every word repeats the Python operation for operation in 32-bit floats, and `tests/verify_lava_lamp_forth.py` runs the script in the real zForth VM and compares the two step for step. Blob *i* keeps its nine fields (x, y, vx, vy, r, T, stuck and two drift phases) in level mailboxes 100 + 10*i*. Each frame adds `DELTA_TIME` to an accumulator and runs whole 1/30 s steps, at most four. The liquid's temperature is a hot layer over the coil, `0.3 + 0.75·e^(−y/0.08) − 0.08·y` (`ll-env`); `exp` and `expm1` are engine words from the [math plan](../plans/2026-11-26-forth-math-words.md). The poster prints words copied from the generated script, and its test checks each against the shipped `wflevels/lava_lamp/lava_lamp.lev`.

**Ours (measured)**, `model.character()` over 20 simulated minutes, six blobs: about 31 % of blob time pooled on the coil, 29 % resting under the cap, 39 % moving; a cycle (one release from the pool to the next) about 175 s; the fastest climb about 0.09 globe heights a second. The poster reads these from the model when it builds. These are game tuning, not measurements of a real lamp.

**The four ways to move it** (plan D6): F1, the Forth model, is what ships. F3, a native word, ships for the pair loop only (`lava-pairs`), after cast1 missed its refresh with the pairs in Forth. F2, a baked tape, survives only as the 150 s warm-up computed at build time so the level opens mid-flow. F4, Jolt rigid bodies, was not used. Shapes are morph targets (rise, fall, squash, neck and two wobbles) driven by the Morph deformer (E1).

## The hero image

**Ours.** `lava-lamp-poster/render_hero.py` renders the shipped scene, `wflevels/lava_lamp/lava_lamp.blend`, in CPU Cycles in the Blender container: each prelit surface becomes an emission of its baked shade times the tint the director writes, the wax is posed as on the engine's first frame (`model.warmed()` through `model.pose()`), Orange lava in Violet water, 21:47 in the base, the level's own camera and 60° view.

## What was not found, or was corrected

Never printed:

- **"Starlight" holes on the Astro.** The plan attributed the starlight holes to the 1963 Astro, from a secondary source. The source found (How Products Are Made) says it of the Lava Lite **Century**. The poster says Century, chipped *other source*. The Mathmos site (mathmos.com) refused or timed out on every request, so no maker's description of the Astro's base was read.
- **The 43 cm height** of the standard Astro and the **40 W bulb**: no source read gives either for the standard lamp.
- **A warm-up of 45 to 90 min**, from hobby pages (engineerfix, geekchamp): not printed. The poster prints only How Products Are Made's "four hours or more" for a first melt.
- **The solid wax's expansion coefficient**: the only figure found was on a hobby site.
- **A US issue date of 1971**, from one user-edited history: Google Patents gives 1968‑06‑11 for US 3,387,396.
- **Where the pub was.** Wikipedia's Mathmos page says Dorset; a search-result summary placed it in Hampshire (that page was not read). The poster says only "a pub".
- **The German trade show's city**: Wikipedia says only "a German trade show", and so does the poster.
