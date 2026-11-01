# Retiring the generic Template OAS type

## Finding

`wfsource/source/oas/template.oas` declares a `Template` actor that inherits `actor.inc` and adds no fields. Its tracked `template.oad` is the generated binary descriptor. The generic type is distinct from the inherited `Template Object` boolean field.

At level load, `Level` puts **any** object with `Template Object = 1` into `_templateObjects` (`level.cc`, the `_oadData->TemplateObject` branch). `Generator` stores an object reference from `Object To Throw` and calls `ConstructTemplateObject` on that referenced object's actual type. The generated dispatch contains no `Template_KIND` or `OadTemplate` case. A search of shipped `.lev` sources found no instance whose type is the generic `Template`; many concrete actor types use the inherited flag.

## Retirement completed, 2026-11-02

Removed the tracked `template.oas` and generated `template.oad`, plus the stale untracked generated `template.ht`. Updated the actor-type index and Q✱bert plan: Generator's `Object To Throw` may reference any concrete type whose level object has `Template Object = 1`.

`wfsource/source/oas/regen-headers.sh` generated all 42 remaining OAS headers and actor dispatch outputs in `/tmp/template-oas-retirement`. The regenerated `objects.c`, `objects.h`, `objects.e`, `objects.inc`, `objects.lc` and `objects.col` match the tracked outputs byte-for-byte; none contains a generic Template actor entry. The source list already excluded Template, so its removal does not renumber actor kinds. Searches found no shipped level using the generic actor type. Representative `smb_w1_1` (coins, powerups and Generator) and `filesys` (Dir, File and Connector templates) levels both rebuilt successfully with the existing OAD schemas. `Template Object`, the level template pool, `Generator` and `ConstructTemplateObject` remain in place.

Representative level rebuilds and device spawning checks remain to be run as part of the broader engine validation; the retirement itself only removes an unused authoring type and descriptor.
