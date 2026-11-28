| Date | Change |
|------|--------|
| [2026-11-24](https://github.com/wbniv/WorldFoundry/commit/7ed6d60c5) | Check in Aquarium and Clocks development build inputs |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/9e4690e0f) | Cuckoo Village: Bavaria mode's reversed hands and parade checked on cast1 across 20:00 |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/b1fc0555a) | Cuckoo Village: Bavaria mode checked on cast1 (form row, Off is Classic, On shows the Bavarian parts) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/451d7adb4) | Cuckoo Village: Bavaria mode (reversed dial and parade, four Bavarian figures, chalet case, dome, lozenge frieze, maypole) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/f955673e6) | Cuckoo Village: candles always on 1 Dec to 6 Jan, and a Candles all year switch for the rest |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/ce49e0835) | Docs: village settings are live, hold A opens them; every 3D clock needs a settings object; TODO for the aquarium gaps; effect tests |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/c81446981) | Cuckoo Village plan: Bavaria mode, Christmas candles, Bavarian seasonal events |

<!--history-meta v1
7ed6d60c5	author	Will Norris
7ed6d60c5	added	25
7ed6d60c5	deleted	4
7ed6d60c5	files	1
9e4690e0f	author	Will Norris
9e4690e0f	added	1
9e4690e0f	deleted	1
9e4690e0f	files	1
9e4690e0f	body	One 215 s record with video (job J-b957f1331ff9) spanning the hour: the hour hand points to 4 where the Classic dial has it at 8, the bird calls, and the four\nfigures run the parade the reversed way (the model fits the figures' positions in four consecutive seconds to 0.07 m in Bavaria mode and 0.55 m in Classic mode).\nThe TODO item moves to Done; the Bavarian numerals at readable size stay unseen.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
b1fc0555a	author	Will Norris
b1fc0555a	added	3
b1fc0555a	deleted	1
b1fc0555a	files	1
b1fc0555a	body	One 140 s record on cast1 with the Clocks APK e37c973b (job J-946137df5b8f): the first form row turns Bavaria mode On, the village shows the\nchalet case, four figures, dome, friezes and maypole; Off is the Classic village. Not seen on the device: the reversed hands in motion and\nthe hourly parade (the record ran outside the hour), and the numerals at readable size.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
451d7adb4	author	Will Norris
451d7adb4	added	5
451d7adb4	deleted	1
451d7adb4	files	1
451d7adb4	body	Bavaria mode (the field read by the director) now changes how the village looks and who performs, not how it works. One sign, +1 Classic\nand -1 Bavaria, turns the hands anti-clockwise and sends the parade the other way round the same route (the schedule, solo turns, bird,\nwindows, candles and camera are unchanged). The cooper, the dirndl figure, the lederhosen figure and the brewer stand on the Classic\nfigures' pivots as twin actors posed from the same calculation; two visibility cells show one set. The Classic numerals become their own\nactor so a reversed dial (anti-clockwise, upright digits) can replace them. The chalet trim (a carved gable with stags, a vine round the\ndial, a heart rail, pinecone weights), a green onion dome, a lozenge frieze with timber trim on six cottages and a spiralled maypole are\npure-Python geometry (bavaria.py) in the village atlas's own tiles. Checked in the real zForth VM (hands and eight figures, field Off, On\nand unanswered) and in the real engine in both modes (check-cuckoo-village.py --compare, new --bavaria); close-ups are Blender renders\n(CUCKOO_REVIEW_RENDER). Not yet run on a device.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
f955673e6	author	Will Norris
f955673e6	added	6
f955673e6	deleted	6
f955673e6	files	1
f955673e6	body	Will, 2026-11-22: "always on dec 1 - jan 6 but can be turned on other times with the switch". The field is\nrenamed from Christmas candles (On/Off, default On, could switch the season's candles off) to Candles all\nyear (Off/On, default Off): the director lights the candle cell in season, or when the switch is On. The .oad\nand header are regenerated (the .oad equals what oas2oad makes), the VM check covers the new rule across\nevery year edge, the plan and the settings table follow. TODO: consider a date-range setting, and more\nDecember events. Still no candle meshes: nothing displays the cell yet.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
ce49e0835	author	Will Norris
ce49e0835	added	16
ce49e0835	deleted	4
ce49e0835	files	1
ce49e0835	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
c81446981	author	Will Norris
c81446981	added	187
c81446981	deleted	0
c81446981	files	1
c81446981	body	Bavaria mode is a CuckooVillageSettings field: carved chalet case, Bavarian\nfigures, a reversed dial and a reversed parade, same timeline and camera.\nChristmas candles show 1 Dec to 6 Jan in both modes. Seasonal events\n(Nikolaus, Krampus, Fasching, Oktoberfest, maypole dressing) come from one\ndate-driven season calendar. Adds mockups, a cleaned concept cut-out, and\nTODO items to investigate an Almabtrieb season and a mountain setting.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
-->
