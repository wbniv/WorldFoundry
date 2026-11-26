"""The six patents on the lava lamp poster, as Google Patents gave them on 2026-11-26.

docs/reference/lava-lamp-research.md ("Patents") holds the locators and what each patent is. make_poster.py prints this
table (panel 04) and make_qr.py writes qr/<key>.svg for each url.
"""

CHECKED = '2026-11-26'

PATENTS = [
    dict(key='GB703924', number='GB 703,924', url='https://patents.google.com/patent/GB703924A/en',
         title='A display device using liquid bubbles in another liquid', who='Donald Dunnet',
         dates='filed 1950-12-21 · published 1954-02-10',
         what='a lamp heats the lower of two liquids; it rises in bubbles, cools and returns. The precursor'),
    dict(key='US3387396', number='US 3,387,396', url='https://patents.google.com/patent/US3387396A/en',
         title='Display devices', who='David George Smith, for Crestworth Ltd',
         dates='filed 1965-03-04 · granted 1968-06-11',
         what='the lava lamp: wax that flows when heated, a heater below, a spiral wire to break surface tension'),
    dict(key='US3689139', number='US 3,689,139', url='https://patents.google.com/patent/US3689139A/en',
         title='Optical projector', who='Alexander and Ilene Astrahan Gross',
         dates='filed 1969-09-22 · granted 1972-09-05',
         what='a projector slide of coloured immiscible fluids. Cites Dunnet'),
    dict(key='US3777379', number='US 3,777,379', url='https://patents.google.com/patent/US3777379A/en',
         title='Aesthetic fluid suspension and its preparation', who='W. Lewellen',
         dates='filed 1969-03-07 · granted 1973-12-11',
         what='a contrasting gel held still inside another gel. Cites Dunnet'),
    dict(key='US4057921', number='US 4,057,921', url='https://patents.google.com/patent/US4057921A/en',
         title='Decorative device', who='Derek William Ball',
         dates='filed 1976-05-24 · granted 1977-11-15',
         what='flat chambers of coloured immiscible fluids that overlap as they move. Cites Dunnet'),
    dict(key='US5732138', number='US 5,732,138', url='https://patents.google.com/patent/US5732138A/en',
         title='Seeding a pseudo-random number generator with a hash of a digitized chaotic system',
         who='Noll, Mende and Sisodiya, for Silicon Graphics',
         dates='filed 1996-01-29 · granted 1998-03-24',
         what='Lavarand: random numbers from pictures of lava lamps'),
]
