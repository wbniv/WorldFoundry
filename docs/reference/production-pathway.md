# Production Pathway

Converted from `docs/Production Pathway.dia` (v0.4).  
Original note: *"Some details could be missing or incorrect. Note that the makefiles which execute these conversions are not shown. Due to limited space not all paths are shown."*

---

## High-level asset funnel

Six asset categories enter the pipeline and converge into two outputs. The Sankey
widths are proportional to the number of distinct data streams — not byte sizes.

```mermaid
sankey-beta

OAS / OAD schemas,Prep,2
Source code,C++ compiler,4
Textures,Geometry + texture pipeline,2
3D geometry,Geometry + texture pipeline,3
Level descriptors,Level compile pipeline,4
levels.txt,cd.pl,1

Prep,C++ compiler,1
Prep,Level compile pipeline,1
Geometry + texture pipeline,Level compile pipeline,5
Level compile pipeline,Per-level IFFs,10
C++ compiler,game executable,5
cd.pl,iffcomp (cd),1
Per-level IFFs,iffcomp (cd),10
iffcomp (cd),cd.iff,11
```

The detailed step-by-step flow follows below.

---

```mermaid
flowchart TD

    oas["*.oas"]
    objects_mac["objects.mac"]
    Prep[/"Prep"\]
    objects_lc["List of object types\noas/objects.lc"]
    oad_iff_txt["Object Attribute Descriptors\noad/*.iff.txt"]
    oas_ht["Object header files\noas/*.ht"]
    editor_lev[/"3D editor with\nattribute editor\n& lev exporter"\]
    levelname_lev["{levelname}.lev"]
    iff2lvl[/"iff2lvl"\]
    objects_id["objects.id"]
    levelname_ini["{levelname}.ini"]
    cpp_compiler[/"C++ compiler"\]
    source_cc["Source files\n*.cc"]
    game_exe["game executable"]
    editor_model[/"3D editor\n(modelling/animation)"\]
    levelname_lvl["{levelname}.lvl"]
    oad_iff["Binary Object Attribute Descriptors\noad/*.iff"]
    iffcomp_oad[/"iffcomp"\]
    textile[/"textile"\]
    textures["textures\n*.tga"]
    execute_game[/"execute game"\]
    cd_iff["Entire game data file\ncd.iff"]
    iffcomp_cd[/"iffcomp"\]
    levels_txt["levels.txt"]
    levelnames_iff["*{levelnames}.iff"]
    iffcomp_lvl[/"iffcomp"\]
    cd_pl[/"cd.pl"\]
    cd_iff_txt["cd.iff.txt"]
    perm_ruv["perm.ruv\nroom*.ruv"]
    perm_tga["perm.tga\nroom*.tga"]
    palperm_tga["palperm.tga\npal*.tga"]
    geometry_iff_txt["{geometry}.iff.txt"]
    matte_tga["matte.map\nmatte.tga"]
    geometry_iff["{geometry}.iff"]
    iffcomp_geo[/"iffcomp"\]
    ram_iff_txt["ram.iff.txt"]
    levelname_lev_bin["{levelname}.lev.bin"]
    iffcomp_lev[/"iffcomp"\]
    asset_inc["asset.inc"]
    prep[/"prep"\]
    ini_prp["ini.prp"]
    anim_iff_txt["{single animation cycle}.iff.txt"]
    geometry_ali["{geometry}.ali"]
    iffcomp_anim[/"iffcomp"\]
    geometry_anim_iff["{geometry with animation}.iff"]

    oas           --> Prep
    objects_mac   --> Prep
    Prep          --> objects_lc
    Prep          --> oad_iff_txt
    Prep          --> oas_ht

    oad_iff_txt   --> iffcomp_oad
    iffcomp_oad   --> oad_iff

    objects_lc    --> editor_lev
    oad_iff       --> editor_lev
    editor_lev    --> levelname_lev

    levelname_lev --> iffcomp_lev
    iffcomp_lev   --> levelname_lev_bin
    levelname_lev_bin --> iff2lvl
    iff2lvl       --> objects_id
    iff2lvl       --> asset_inc
    iff2lvl       --> levelname_lvl

    asset_inc     --> prep
    ini_prp       --> prep
    prep          --> levelname_ini

    levelname_ini --> textile
    textures      --> textile
    textile       --> perm_ruv
    textile       --> perm_tga
    textile       --> palperm_tga

    perm_ruv      --> iffcomp_lvl
    perm_tga      --> iffcomp_lvl
    palperm_tga   --> iffcomp_lvl
    levelname_lvl --> iffcomp_lvl
    matte_tga     --> iffcomp_lvl
    geometry_iff  --> iffcomp_lvl
    ram_iff_txt   --> iffcomp_lvl
    geometry_anim_iff --> iffcomp_lvl
    iffcomp_lvl   --> levelnames_iff

    textures      --> editor_model
    editor_model  --> geometry_iff_txt
    editor_model  --> anim_iff_txt
    geometry_iff_txt --> iffcomp_geo
    iffcomp_geo   --> geometry_iff
    geometry_ali  --> iffcomp_anim
    anim_iff_txt  --> iffcomp_anim
    iffcomp_anim  --> geometry_anim_iff

    oas_ht        --> cpp_compiler
    source_cc     --> cpp_compiler
    cpp_compiler  --> game_exe

    levels_txt    --> cd_pl
    cd_pl         --> cd_iff_txt
    cd_iff_txt    --> iffcomp_cd
    levelnames_iff --> iffcomp_cd
    iffcomp_cd    --> cd_iff

    game_exe      --> execute_game
    cd_iff        --> execute_game
```

---

> ⚠️ `{geometry}.ali` → animated geometry conversion is noted in the original as **not currently automated**.
