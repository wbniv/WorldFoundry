# The tide at Bangkok: sources, calculation and accuracy

**Research for the Tide Harbour clock and its A3 poster, 2026-11-21.** Written first, as the [seahorse poster](seahorse-biomechanics-poster/README.md) was: the poster prints only what this document supports. The plan is [Tide Harbour](../plans/2026-11-21-tide-harbour-clock.md).

Every claim carries one label:

- **verified**: the source was read, and it says this about this station or river;
- **other source**: read, but about a different place or a model, and used only as stated;
- **ours (measured)**: a result we computed from the sources, with the script that computes it.

What could not be confirmed is listed [at the end](#what-was-not-found) and is never printed on the poster.

## What we need

A harbour scene on the Chao Phraya at Bangkok whose water level, boats and gauge follow the real tide for the date and time on the clock. That needs a function from a date and a time to a water height, good enough that a person who knows the river would not call it wrong. It does not need to be a navigation product.

## The source

**Verified.** The Royal Thai Navy Hydrographic Department publishes, for every day of the year, the predicted time and height of each high and low water at 31 stations. It posts one PDF per station per year on its tide service pages ([2026](https://hydro.navy.mi.th/sevicetide), [2027](https://hydro.navy.mi.th/servicetide2570)); no login is needed. Station **HD, Royal Thai Navy Headquarters (Bangkok Metropolitan)**, at 13° 44′ 36″ N, 100° 29′ 25″ E, is on the river inside the city and is the one used here. The same page lists Bangkok Port (Khlong Toei side, `BH`) and Bangkok Bar at the river mouth (`BB`).

- Heights are printed as "predicted in metres above the lowest low water" (the table's footer, English line).
- The department's own account of the method: it provides tide tables for 29 sites and uses harmonic constants derived from one year of gauge observations ([IHO North Indian Ocean Hydrographic Commission, 23rd meeting, Thailand national report](https://iho.int/uploads/user/Inter-Regional%20Coordination/RHC/NIOHC/NIOHC23/NIOHC23-8.1I_2024_National%20Report%20Thailand.pdf), the paragraph on tide tables); and uses 112 harmonic constituents with software from the Tidal Laboratory, Flinders ([GLOSS, "Tidal work in Thailand", 2001](https://gloss-sealevel.org/sites/gloss/files/publications/documents/thailand_2001.pdf), section 3). The constants themselves are not published (see below).
- Tide gauges at the river mouth go back a century: observations at Bangkok Bar began in 1904 (GLOSS report, section 2). [PSMSL station 287](https://psmsl.org/data/obtaining/stations/287.php) lists Bangkok Bar at 13.45° N, 100.6° E with monthly means for 1926 to 2022, flagged by PSMSL as "not research quality data". It carries no hourly record, so it cannot be fitted.

## What the 2026 table shows

**Ours (measured)**, read from `HD2026.pdf` with `wflevels/tide_harbour/tide_fit/parse_hd.py`:

| Quantity | 2026 | 2027 |
|---|---|---|
| Listed highs and lows | 1225 | 1222 |
| Lowest listed height | 0.53 m | 0.55 m |
| Highest listed height | 3.33 m | 3.25 m |
| Days with one high and one low | 92 | 95 |
| Days with two highs and two lows | 238 | 234 |
| Days with a different count (one, three) | 35 | 36 |

A **mixed** tide, as the station's two-high days and one-high days both occur in the same month. Where a day has one high, the curve has a flat shoulder in place of the second high, so the table lists no event there; consecutive listed events are therefore up to 17 hours apart. This is not a parsing fault: all 365 days parse for each year, high and low alternate without exception, and eight days (1, 2, 3, 8, 9, 10 January, 1 February, 1 March) were copied by hand from the page text into `tests/test_tide_constants.py`, which scores the shipped constants against them, so the check does not depend on our parser.

## The time zone, measured

The table does not say which clock it uses. **Ours (measured):** `check_time_zone.py` fits harmonic constants to the observed 2025 hourly sea level at Ko Lak ([UHSLC station 328](https://uhslc.soest.hawaii.edu/data/)), predicts 2026, and slides the department's published Ko Lak events (`KL2026.pdf`) against the prediction. Median mismatch is **11 minutes with the table 7.0 hours ahead of the record** and 308 minutes with no shift; the next-best half-hour shifts are 22 and 40 minutes. Ko Lak is strongly diurnal, so a 7-hour shift is 105 degrees of the K1 phase and cannot be confused with another offset.

**Verified:** the GLOSS station handbook gives Ko Lak's time zone as "105E, GMT + 7hrs" ([GLOSS handbook, station 39](https://www.bodc.ac.uk/resources/inventories/gloss_handbook/stations/39/)). **Not verified:** which clock the UHSLC hourly file itself uses; none of the UHSLC pages read says. The conclusion that the table is in **Thai local time, UTC+7** therefore rests on the record being in GMT, as such archives conventionally are, and on 7 hours matching Thailand's own zone; any other reading needs an offset such as GMT+14 that no one uses.

## The calculation

A tide is a sum of cosines, one per astronomical cause. Each constituent has a speed fixed by the motions of the Moon and Sun, an amplitude and a phase that depend on the place. **Verified:** NOAA states the prediction formula in this form, `h = Ho + Σ f·H·cos[a·t + (V0+u) − K]`, with `a` the constituent's speed and `K` its epoch, in Local Standard Time or GMT ([NOAA, About Harmonic Constituents](https://tidesandcurrents.noaa.gov/about_harmonic_constituents.html)). Ours is the same sum with the nodal terms `f` and `u` set to 1 and the phase folded into one number:

> h(t) = z0 + Σ A<sub>k</sub> · cos( 2π · (f<sub>k</sub> · t + φ<sub>k</sub>) )

- **Speeds** come from Doodson numbers: the lunar day, the month, the year, the lunar perigee, the node and the solar perigee combined with small integers. `constituents.py` builds 55 standard constituents this way. **Verified:** it agrees to 1e-7 degrees per hour with the speeds in NOAA's constituent tables for M2, K1, O1, S2, N2, P1, Q1, K2, MK3, M4 and M6 ([NOAA, NOS CO-OPS 3, *Tidal Analysis and Predictions*](https://tidesandcurrents.noaa.gov/publications/Tidal_Analysis_and_Predictions.pdf), Tables 3.2 and A.2), which also give M2 28.9841042 degrees per hour, 12.4206 h, and P1 14.9589314, 24.0659 h. The periods used in this document (K1 23.93 h and O1 25.82 h, once a day; M2 12.42 h and S2 12.00 h, twice a day) are those speeds converted: **ours (computed)**.
- **Shallow-water compound tides** are sums and differences of the main constituents (for example MK3, MS4, 2SM6). A river and a shelf generate them. `constituents.compound()` adds every combination of up to three terms, then drops any within 0.03 degrees per hour of another (the resolving power of one year), leaving **171 candidates**.
- **The fit.** The table lists only extrema, so no curve exists to fit. At every listed event two things are known: the height is the listed height, and the slope is zero. Both are linear in the unknown cosine and sine coefficients, so one linear least squares gives all of them. Weights: a 2 cm height error counts as much as a 3 mm per hour slope error (about 10 minutes at a peak). The 64 largest constituents are kept and refitted. Result: `wflevels/tide_harbour/tide_constants.json`.

### The result, with its limits

**Ours (measured).** Constants fitted to one year and scored on the other, which the fit never saw:

| Fitted on | Scored on | Median height error | 90th percentile | Largest |
|---|---|---|---|---|
| 2026 | 2027 | 4.5 cm | 11.3 cm | 22.6 cm |
| 2027 | 2026 | 4.1 cm | 10.6 cm | 21.5 cm |

The shipped constants use both years: 5.2 cm median and 11.4 cm at the 90th percentile over all 2447 events. The tide's range at this station is about 2.8 m between extremes of the year, so a typical error is under 2 percent of it.

How many constituents are enough? Fitted to 2026 and scored on unseen 2027:

| Constituents kept | 6 | 12 | 24 | 32 | 48 | 64 | 96 | 171 |
|---|---|---|---|---|---|---|---|---|
| Median height error (cm) | 28.0 | 21.3 | 10.6 | 8.2 | 5.6 | 4.5 | 3.8 | 3.7 |

A handful of constituents gets the look; it takes about 48 to get within 6 cm.

Largest of the 64 (amplitude, period): K1 50.0 cm 23.93 h; M2 36.3 cm 12.42 h; O1 30.9 cm 25.82 h; S2 23.1 cm 12.00 h; Sa 17.1 cm one year; P1 13.2 cm 24.07 h; K2 8.5 cm 11.97 h; Mf 7.8 cm 13.66 days. The form factor (K1 + O1) / (M2 + S2) is **1.36**, in the "mixed, mainly semidiurnal" class (0.25 to 1.5) by the rule in [Aungsakul et al. 2011](https://wjst.wu.ac.th/index.php/wjst/article/view/128), which classifies the same station as 1.06, the same class.

**Cautions.** (1) Time errors are larger than the height errors suggest: at a flat peak a few centimetres move the extremum by up to an hour or two, so "the time of high water" is only good to tens of minutes where the tide is flat; the median is 13 minutes fitted on 2026 and scored on 2027, and 11 the other way. (2) The fit is to published predictions, not to observations or to the department's constants, so it can be no better than they are. (3) There is no nodal correction: NOAA's formula carries a yearly amplitude factor `f` that ours sets to 1 ([NOAA](https://tidesandcurrents.noaa.gov/about_harmonic_constituents.html)). One year ahead showed no loss (3.7 against 3.3 cm); the department publishes each year, so refitting yearly is cheap. (4) Sa (17 cm) is the annual cycle of the mean level, which in a river mixes the sea's seasonal level and the river's discharge; two years cannot separate them. (5) The compound set was chosen by us.

## The paper that gave a form factor

**Other source.** Aungsakul, Jaroensutasinee and Jaroensutasinee, "Numerical Study of Principal Tidal Constituents in the Gulf of Thailand and the Andaman Sea", *Walailak J. Sci. & Tech.* 4(1), 95–109, 2011 ([article](https://wjst.wu.ac.th/index.php/wjst/article/view/128), CC BY-NC-ND 4.0). Table 3 gives form factors for 21 stations; Royal Thai Navy Headquarters is 1.06, "Mixed, Semidiurnal", and its neighbours Bang Pakong 1.34, Tha Chin 1.41 and Mae Klong 1.38. Figure 2(e), read by eye, shows the four constituents at that station at roughly O1 0.12 m, K1 0.21 m, M2 0.19 m, S2 0.12 m (about ±0.02 m). **These amplitudes are not used**: they come from the paper's numerical model, and the table-derived K1 is 2.4 times larger. The paper's form factor is used only as the second, independent statement of the tide type.

## What was not found

- **The department's own harmonic constants for Bangkok.** Not located on any public page read. The fit above stands in for them and says so.
- **The licence of the tables.** Pages are public and were fetched once each with a pause between requests; no terms of use were found on the pages read. We embed fitted constants, not the tables. Whether the department wants attribution is not known. Attribution is given.
- **Observed hourly water level in the city.** The only hourly record found near Bangkok is Ko Lak's, on the Gulf's west coast, used only for the clock check.
- **Two papers behind a paywall or a dead mirror.** The Thammasat analytical model of the Chao Phraya tide and the Springer paper on tidal-level trends in the Gulf of Thailand ([abstract only](https://link.springer.com/article/10.1007/s12601-020-0039-1)) were not readable; nothing from them is used.
- **Sunrise, sunset and the moon.** Deliberately not researched ([plan decision D12](../plans/2026-11-21-tide-harbour-clock.md#decisions)): the scene computes the sun's rise and set from a formula and checks it in the build, and makes no claim about the moon. The poster says nothing about either.
- **The river's discharge effect.** The fit absorbs it into Sa and into the compound terms; it is not modelled.

## Reproduce

```sh
bash wflevels/tide_harbour/tide_fit/fetch_sources.sh            # one request per file, a pause between
python3 -I wflevels/tide_harbour/tide_fit/check_time_zone.py
python3 -I wflevels/tide_harbour/tide_fit/make_constants.py --n 64
python3 -m pytest -q tests/test_tide_constants.py
```

The A3 poster built from this research is in [chao-phraya-tide-poster](chao-phraya-tide-poster/README.md).
