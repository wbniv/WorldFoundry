"""Source-backed draft claims. This dataset is incomplete and must fail closed.

Locations are part of the evidence: do not promote a laboratory result or an
observation from another region into a statement about Gulf wild behaviour.
"""
SOURCES = {
    'crab': {'url': 'https://li01.tci-thaijo.org/index.php/JFE/article/view/263011', 'cite': 'Wisespongpand et al. 2024', 'where': 'Koh Tao and Koh Nang Yuan', 'about': 'coral crabs'},
    'worms': {'url': 'https://d-nb.info/1122621531/34', 'cite': 'van der Schoot et al. 2016', 'where': 'Koh Tao', 'about': 'worms and clams'},
    'wormfood': {'url': 'https://sta.uwi.edu/fst/lifesciences/sites/default/files/lifesciences/documents/ogatt/Spirobranchus_giganteus%20-%20Christmas%20Tree%20Worm.pdf', 'cite': 'UWI Christmas tree worm profile', 'where': 'Trinidad and Tobago', 'about': 'related worm feeding'},
    'duster': {'url': 'https://www.eerc.ntu.edu.tw/2019asiambs/wp-content/uploads/2019/11/SymposiumProgramFull.pdf', 'cite': 'Rongprakhon et al. 2019', 'where': 'western Gulf, p. 153', 'about': 'reef-flat survey'},
    'crinoid': {'url': 'https://journal.nsm.or.th/en/node/161', 'cite': 'Had Khanom echinoderm survey', 'where': 'southern Gulf', 'about': 'echinoderms'},
    'crinoidpalau': {'url': 'https://micronesica.org/sites/default/files/ecology_and_distrubution_of_the_shallow-water_crinoids_of_palau_and_guam_micronesica_vol._16_no._1_june_1980o.pdf', 'cite': 'Meyer and Macurda 1980', 'where': 'Palau, pp. 85–86', 'about': 'feather-star activity and feeding posture'},
    'poritesfood': {'url': 'https://pubmed.ncbi.nlm.nih.gov/32753190/', 'cite': 'Sangmanee et al. 2020', 'where': 'Okinawa, laboratory incubation', 'about': 'Porites plankton feeding'},
    'poritesmucus': {'url': 'https://research-repository.uwa.edu.au/files/21429380/THESIS_DOCTOR_OF_PHILOSOPHY_BESSELL_BROWNE_Pia_2017.pdf', 'cite': 'Bessell-Browne et al. 2017', 'where': 'Western Australia', 'about': 'Porites mucus and sediment'},
    'tabledef': {'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4320547/', 'cite': 'Hemond et al. 2014', 'where': 'Caribbean', 'about': 'related Acropora nematocysts'},
    'goniofood': {'url': 'https://pubmed.ncbi.nlm.nih.gov/34827743/', 'cite': 'Ding et al. 2021', 'where': 'Taiwan, aquarium experiment', 'about': 'Goniopora feeding'},
    'turbimucus': {'url': 'https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0216248', 'cite': 'Jones et al. 2019', 'where': 'Western Australia', 'about': 'coral mucus and sediment'},
    'goniosense': {'url': 'https://pubmed.ncbi.nlm.nih.gov/12242/', 'cite': 'Anderson 1976', 'where': 'laboratory', 'about': 'Goniopora polyp retraction'},
    'spongechem': {'url': 'https://pubmed.ncbi.nlm.nih.gov/23829580/', 'cite': 'Antifouling sterols study', 'where': 'Vietnam, laboratory', 'about': 'sponge compound assays'},
    'nudi': {'url': 'https://dmcrth.dmcr.go.th/lmcr/detail/14583/', 'cite': 'DMCR reef survey', 'where': 'lower Gulf', 'about': 'reef observations'},
    'corals': {'url': 'https://www.apn-gcr.org/wp-content/uploads/2020/09/41f9a984933ec9bf0cb1e9b36a1e3e0b.pdf', 'cite': 'Eastern Gulf reef assessment', 'where': 'eastern Gulf, section 4.1.1', 'about': 'reef corals'},
    'checklist': {'url': 'https://repository.naturalis.nl/pub/800405/Mehrotra-2024-Parasites-or-predators-A.pdf', 'cite': 'Mehrotra et al. 2024', 'where': 'Koh Tao, Table 1', 'about': 'coral distribution'},
    'sarco': {'url': 'https://academic.oup.com/icesjms/article/66/7/1515/657058', 'cite': 'Chavanich et al. 2009', 'where': 'upper Gulf', 'about': 'soft coral'},
    'sarcofood': {'url': 'https://ojs.unimal.ac.id/index.php/acta-aquatica/article/view/2526', 'cite': 'Aksari et al. 2020', 'where': 'Bali, aquarium experiment', 'about': 'soft-coral feeding'},
    'sarcodef': {'url': 'https://agris.fao.org/search/ar/records/65df50b96eef00c2cea26a09', 'cite': 'Hoang et al. 2022', 'where': 'central Vietnam', 'about': 'soft-coral feeding deterrents'},
    'tablefood': {'url': 'https://sanctuaries.noaa.gov/media/docs/20231129-coral-reef-organisms-table.pdf', 'cite': 'NOAA coral reef organisms', 'where': 'American Samoa', 'about': 'table coral feeding'},
    'sponge': {'url': 'https://www.cambridge.org/core/journals/journal-of-the-marine-biological-association-of-the-united-kingdom/article/abs/species-diversity-of-marine-sponges-dwelling-in-coral-reefs-in-had-khanommo-ko-thale-tai-national-park-nakhon-si-thammarat-province-thailand/077965DFB097BE9B25EBF03B3B5A2B32', 'cite': 'Had Khanom sponge survey', 'where': 'southern Gulf', 'about': 'sponges'},
    'spongefood': {'url': 'https://repository.kaust.edu.sa/bitstreams/99febf76-c8b5-41c3-a119-3687ad31e57f/download', 'cite': 'Wooster et al.', 'where': 'Red Sea', 'about': 'sponge feeding'},
    'humbug': {'url': 'https://bioflux.com.ro/docs/2023.3296-3315.pdf', 'cite': 'Dat et al. 2023', 'where': 'Tho Chu Island, Gulf, Table 1', 'about': 'reef-fish checklist'},  # D. reticulatus (Will, 2026-11-09)
    'geography': {'url': 'https://tile.loc.gov/storage-services/service/gdc/gdcovop/2023331201/2023331201.pdf', 'cite': 'East Asian Seas atlas', 'where': 'Gulf of Thailand entry', 'about': 'geography'},
    'survey': {'url': 'https://li01.tci-thaijo.org/index.php/JFE/article/download/263011/178967/1052230', 'cite': 'Wisespongpand et al. 2024', 'where': 'Koh Tao', 'about': 'reef survey'},
    'bleaching1998': {'url': 'https://www.dmcr.go.th/detailLib/651', 'cite': 'Thai DMCR bleaching report', 'where': 'Thailand section', 'about': 'reef history'},
    'bleaching2024': {'url': 'https://ph02.tci-thaijo.org/index.php/RIST/article/view/260575', 'cite': 'Ko Ngam Noi coral mortality assessment', 'where': 'western Gulf', 'about': '2024 bleaching'},
    'bleaching2010': {'url': 'https://castjournals.cast.org.cn/joweb/aos/EN/1245664136378564803', 'cite': 'Pengsakun et al. 2019', 'where': 'inner Gulf', 'about': 'coral bleaching'},
    'tubafood': {'url': 'https://sta.uwi.edu/fst/lifesciences/sites/default/files/lifesciences/documents/ogatt/Tubastraea_coccinea%20-%20Orange%20Cup%20Coral.pdf', 'cite': 'UWI orange cup coral profile', 'where': 'Trinidad and Tobago', 'about': 'cup coral feeding'},
    'tubadef': {'url': 'https://pubmed.ncbi.nlm.nih.gov/32128117/', 'cite': 'Kitahara et al. 2020', 'where': 'Brazil', 'about': 'cup coral nematocysts'},
    'shrimpgulf': {'url': 'https://chm-thai.onep.go.th/wp-content/uploads/2021/09/ONEP_V05.pdf', 'cite': 'ONEP crustacean checklist', 'where': 'Chon Buri, p. 29', 'about': 'shrimp occurrence'},
    'shrimplab': {'url': 'https://www.nature.com/articles/s41598-018-32293-6.pdf', 'cite': 'Vaughan et al. 2018', 'where': 'Australia, laboratory', 'about': 'parasite reduction'},
    'shrimpshelter': {'url': 'https://libknowledge.nmns.edu.tw/nmns/upload/bulletin/000000202/209000c/201212-41.pdf', 'cite': 'Chen and Huang 2012', 'where': 'southern Taiwan, p. 43', 'about': 'shrimp cleaning station'},
    'turbiwork': {'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9600528/', 'cite': 'Turbinaria feeding study', 'where': 'Red Sea, laboratory', 'about': 'other Turbinaria species feeding'},
    'dusterfood': {'url': 'https://invasions.si.edu/nemesis/species_summary/-529', 'cite': 'Smithsonian NEMESIS', 'where': 'genus account', 'about': 'fan worm diet'},
    'dusterdef': {'url': 'https://collections.museumsvictoria.com.au/species/8516', 'cite': 'Museums Victoria', 'where': 'genus account', 'about': 'fan worm withdrawal'},
    'clamdef': {'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4231208/', 'cite': 'Soo and Todd 2014', 'where': 'giant clam review', 'about': 'shadow response'},
    'nudifood': {'url': 'https://link.springer.com/article/10.1007/s00338-010-0698-y', 'cite': 'van Alphen et al. 2011', 'where': 'Halmahera', 'about': 'sponge feeding'},
    'nudidef': {'url': 'https://repository.si.edu/bitstreams/4ee3de11-04c8-4bce-93c9-8588570c6d68/download', 'cite': 'Ritson-Williams and Paul 2007', 'where': 'Palau specimens; Guam field assay', 'about': 'fish feeding deterrence'},
    'hermitfood': {'url': 'https://www.jto.ac.cn/EN/abstract/abstract11363.shtml', 'cite': 'Jia et al. 2024', 'where': 'Nansha Islands', 'about': 'hermit diet'},
    'hermitshell': {'url': 'https://nationalzoo.si.edu/animals/striped-hermit-crab', 'cite': 'Smithsonian striped hermit crab', 'where': 'Atlantic; group account', 'about': 'shell protection'},
    'guarddef': {'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4183949/', 'cite': 'McKeon and Moore 2014', 'where': 'Moorea', 'about': 'guard crab defence'},
    'plankton': {'url': 'https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2022.964725/full', 'cite': 'Shmuel et al. 2022', 'where': 'Red Sea', 'about': 'guard crab feeding'},
    'wormwithdraw': {'url': 'https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecy.2668', 'cite': 'Hoeksema et al. 2019', 'where': 'Koh Tao', 'about': 'tube worms'},
    'fishmotion': {'url': 'https://www.vliz.be/imisdocs/publications/ocrd/361685.pdf', 'cite': 'Boute et al. 2020', 'where': 'flow-tank study', 'about': 'boxfish locomotion'},
    'fishcoral': {'url': 'https://www.nature.com/articles/s41598-020-73979-0.pdf', 'cite': 'Pratchett et al. 2020', 'where': 'Lizard Island, Australia', 'about': 'coral-associated fish'},
    'toxin': {'url': 'https://www.mrc.gov.mv/assets/Uploads/fishes-of-the-maldives.pdf', 'cite': 'Fishes of the Maldives', 'where': 'Maldives', 'about': 'boxfish toxin'},
    'fringing': {'url': 'https://www.scesap.org/ce_archive/ce2017/scott2017a.pdf', 'cite': 'Scott et al. 2017', 'where': 'Koh Tao, Fig. 2', 'about': 'reef forms'},
    'boxfish': {'url': 'https://ph02.tci-thaijo.org/index.php/RIST/article/view/247959', 'cite': 'Sutthacheep 2022', 'where': 'Hin Khao, Koh Tao', 'about': 'boxfish occurrence'},
}

def claim(role, text='', source=None, status='unverified'):
    return {'role': role, 'text': text, 'src': [source] if source else [], 'status': status}

def card(key, name, taxon, kind, source=None):
    gulf = claim('gulf', 'Recorded in the Gulf of Thailand.' if source else '', source, 'verified' if source else 'unverified')
    return {'draw': key, 'name': name, 'taxon': taxon, 'kind': kind,
            'claims': [gulf, claim('eats'), claim('defends'), claim('tank')]}

CARDS = [
    card('xmas', 'Christmas tree worm', 'Spirobranchus sp.', 'moves', 'worms'),
    card('duster', 'Feather duster', 'Sabellastarte sp.', 'moves', 'duster'),
    card('crinoid', 'Feather star', 'Lamprometra palmata', 'moves', 'crinoid'),
    card('clam', 'Fluted giant clam', 'Tridacna squamosa', 'moves', 'worms'),
    card('shrimp', 'Banded coral shrimp', 'Stenopus hispidus', 'moves', 'shrimpgulf'),
    card('nudi', 'Nudibranch', 'Phyllidia varicosa', 'moves', 'nudi'),
    card('hermit', 'Hairy hermit crab', 'Dardanus lagopodes', 'moves', 'survey'),
    card('porites', 'Boulder coral', 'Porites lutea', 'builds', 'survey'),
    card('table', 'Table coral', 'Acropora sp.', 'builds', 'survey'),
    card('gonio', 'Flowerpot coral', 'Goniopora sp.', 'builds', 'corals'),
    card('sarco', 'Leather coral', 'Sarcophyton sp.', 'builds', 'sarco'),
    card('tuba', 'Sun coral', 'Tubastraea coccinea', 'builds', 'checklist'),
    card('turbi', 'Scroll coral', 'Turbinaria sp.', 'builds', 'corals'),
    card('sponge', 'Barrel sponge', 'Xestospongia testudinaria', 'builds', 'sponge'),
    card('crab', 'Guard crab', 'Trapezia cymodoce', 'guards', 'crab'),
]
HABITAT = [
    claim('habitat', 'The Gulf is a semi-enclosed sea, with an average depth of about 45 m.', 'geography', 'verified'),
    claim('habitat', 'A Koh Tao reef survey sampled sites from 5 to 14 m deep.', 'survey', 'verified'),
    claim('habitat', 'Massive Porites dominated most inshore sites surveyed in the eastern Gulf.', 'corals', 'verified'),
    claim('habitat', 'Gulf reefs bleached severely in 1998; Ko Ngam Noi was also affected in 2024.', 'bleaching1998', 'verified'),
    claim('habitat', 'Inner-Gulf monitoring found bleaching in 2010 and 2011, varying by coral taxon.', 'bleaching2010', 'verified'),
    claim('habitat', 'Koh Tao includes fringing reefs, including those at Mango Bay.', 'fringing', 'verified'),
    claim('habitat', 'Some inner-Gulf coral communities near river mouths experience high turbidity.', 'bleaching2010', 'verified'),
]
FISHES = [
    {'key': 'humbug', 'name': 'Reticulated dascyllus', 'taxon': 'Dascyllus reticulatus', 'claims': [claim('gulf', 'Recorded in the Gulf of Thailand.', 'humbug', 'verified'), claim('behaviour')]},
    {'key': 'boxfish', 'name': 'Yellow boxfish', 'taxon': 'Ostracion cubicus', 'claims': [claim('gulf', 'Recorded at Koh Tao in the Gulf of Thailand.', 'boxfish', 'verified'), claim('behaviour'), claim('husbandry')]},
]

# Authored effects describe the design, not observed animal behaviour. They
# are kept separate from the Gulf-occurrence and biology claims above.
_TANK = {
    'xmas': 'In the planned tank, each crown retracts as the boxfish approaches.',
    'duster': 'In the planned tank, the fan will furl and reopen.',
    'crinoid': 'In the planned tank, the feather star will wave its arms.',
    'clam': 'In the planned tank, the mantle will move and the valves partly close.',
    'shrimp': 'In the planned tank, shrimp will visit a hovering boxfish.',
    'nudi': 'In the planned tank, the nudibranch will follow a slow path.',
    'hermit': 'In the planned tank, the hermit will walk with its shell.',
    'porites': 'In the planned tank, the boulder will host worm crowns.',
    'table': 'In the planned tank, the plate forms part of the rockscape.',
    'gonio': 'In the planned tank, the flowerpot polyps will sway.',
    'sarco': 'In the planned tank, the leather coral will slowly sway.',
    'tuba': 'In the planned tank, cup corals will hang inside the cave.',
    'turbi': 'In the planned tank, scrolls form part of the static reef.',
    'sponge': 'In the planned tank, the sponge sits on the rockscape.',
    'crab': 'In the planned tank, the crab will raise its claws near the boxfish.',
}
for _card in CARDS:
    _card['claims'][3] = claim('tank', _TANK[_card['draw']], status='ours')

CARDS[0]['claims'][2] = claim('defends', 'The worm can withdraw into its tube.', 'wormwithdraw', 'verified')
CARDS[0]['claims'][1] = claim('eats', 'A related Christmas tree worm filters plankton and detritus.', 'wormfood', 'other-region')
CARDS[14]['claims'][1] = claim('eats', 'Guard crabs were observed catching plankton in the Red Sea.', 'plankton', 'other-region')
FISHES[0]['claims'][1] = claim('behaviour', 'At Lizard Island, reticulated dascyllus were found mostly on branching Pocillopora corals.', 'fishcoral', 'other-region')
FISHES[1]['claims'][2] = claim('husbandry', 'A Maldives fish guide notes that alarmed boxfish can produce a skin toxin.', 'toxin', 'other-region')
FISHES[1]['claims'][1] = claim('behaviour', 'Its rigid body is manoeuvred with its fins; the tail can stabilize or steer.', 'fishmotion', 'other-region')
CARDS[14]['claims'][2] = claim('defends', 'Other Trapezia species defended host corals against predators in Moorea experiments.', 'guarddef', 'other-region')
HABITAT[3]['src'].append('bleaching2024')
CARDS[1]['claims'][2] = claim('defends', 'A genus account describes crown retraction when disturbed.', 'dusterdef', 'other-region')
CARDS[3]['claims'][2] = claim('defends', 'Fluted giant clams can respond to shadows and touch.', 'clamdef', 'other-region')
CARDS[5]['claims'][1] = claim('eats', 'At Halmahera, this nudibranch was observed feeding on a sponge.', 'nudifood', 'other-region')
CARDS[5]['claims'][2] = claim('defends', 'Extracts from Palau animals deterred fish feeding in Guam field tests.', 'nudidef', 'other-region')
CARDS[6]['claims'][1] = claim('eats', 'At Nansha, sampled hermits ate algae and bryozoans.', 'hermitfood', 'other-region')
CARDS[3]['claims'][1] = claim('eats', 'Giant clams filter food and receive nutrients from photosynthetic symbionts.', 'clamdef', 'other-region')
CARDS[11]['claims'][1] = claim('eats', 'Orange cup coral captures zooplankton with stinging tentacles.', 'tubafood', 'other-region')
CARDS[1]['claims'][1] = claim('eats', 'A Sabellastarte account lists phytoplankton and detritus as food.', 'dusterfood', 'other-region')
CARDS[4]['claims'][1] = claim('eats', 'In a laboratory study this shrimp reduced some fish parasites.', 'shrimplab', 'other-region')
CARDS[4]['claims'][2] = claim('defends', 'At a Taiwan cleaning station, it waited in crevices or shelter exits.', 'shrimpshelter', 'other-region')
CARDS[2]['claims'][1] = claim('eats', 'In Palau, this feather star formed a filtration fan across the current.', 'crinoidpalau', 'other-region')
CARDS[2]['claims'][2] = claim('defends', 'In Palau, it remained hidden in crevices or under coral heads by day.', 'crinoidpalau', 'other-region')
CARDS[7]['claims'][1] = claim('eats', 'Okinawan colonies consumed tiny plankton in laboratory incubations.', 'poritesfood', 'other-region')
CARDS[9]['claims'][2] = claim('defends', 'In experiments, another Goniopora species retracted polyps after stimulation.', 'goniosense', 'other-region')
CARDS[13]['claims'][2] = claim('defends', 'Compounds from Vietnamese specimens inhibited bacterial adhesion in laboratory tests.', 'spongechem', 'other-region')
CARDS[13]['claims'][1] = claim('eats', 'In the Red Sea, these sponges consumed dissolved organic matter and detritus.', 'spongefood', 'other-region')
CARDS[12]['claims'][1] = claim('eats', 'Another Turbinaria species consumed prey in a Red Sea experiment.', 'turbiwork', 'other-region')
CARDS[8]['claims'][1] = claim('eats', 'A table coral species eats plankton and receives sugars from symbiotic algae.', 'tablefood', 'other-region')
CARDS[10]['claims'][1] = claim('eats', 'Cultured Sarcophyton consumed brine shrimp larvae in a Bali experiment.', 'sarcofood', 'other-region')
CARDS[10]['claims'][2] = claim('defends', 'In Vietnam, extracts from some Sarcophyton species deterred feeding fish.', 'sarcodef', 'other-region')
CARDS[11]['claims'][2] = claim('defends', 'Brazilian specimens have stinging capsules containing predicted toxins.', 'tubadef', 'other-region')
CARDS[6]['claims'][2] = claim('defends', 'Many hermit crabs use gastropod shells as protection.', 'hermitshell', 'other-region')
CARDS[7]['claims'][2] = claim('defends', 'Western Australian Porites colonies shed mucus sheets carrying sediment.', 'poritesmucus', 'other-region')
CARDS[8]['claims'][2] = claim('defends', 'Caribbean Acropora studies describe stinging cells used for defense.', 'tabledef', 'other-region')
CARDS[9]['claims'][1] = claim('eats', 'In captivity, G. columna had microalgae and yeast in its body cavities after feeding.', 'goniofood', 'other-region')
CARDS[12]['claims'][2] = claim('defends', 'Some Turbinaria corals used mucus while exposed to sediment in Western Australia.', 'turbimucus', 'other-region')


# Neutral headings avoid inferring defensive function from observations or assays.
for _index, _label in ((2, "Shelter"), (4, "Shelter"), (7, "Sediment"),
                       (9, "Response"), (11, "Lab finding"), (12, "Sediment"),
                       (13, "Lab finding")):
    CARDS[_index]["claims"][2]["label"] = _label
