---
name: loanword-diacritics
description: "Preserve original-language diacritics on French and Spanish loanwords in English prose — naïve, résumé, jalapeño, El Niño, etc."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac975391-be78-4e9a-9979-d9fe03148827
---

In English prose, preserve the original-language diacritics on French and Spanish loanwords. Don't anglicize them by stripping the accent or tilde.

**Why:** User cares about this orthographic convention; flagged "naive" (correction: **naïve**) in `docs/investigations/2026-05-23-fuzzy-logic-visualization-gaps-critique.md` on 2026-05-23, then explicitly extended the scope from French to Spanish ñ words in the same conversation.

**How to apply:** Apply throughout prose — investigation docs, plans, code comments, commit messages, conversational replies. Identifiers/code stay ASCII; the rule is about prose. When unsure for a less-common word, default to the diacritic form.

## French inventory

### Diaeresis (¨)
- **naïve**, **naïvely**, **naïveté**
- **Noël** (proper noun)

### Acute (´)
- **résumé** (CV)
- **café**, **fiancé** (m), **fiancée** (f)
- **déjà vu**
- **élite**
- **exposé**, **décor**, **entrée**, **soirée**
- **protégé** (m), **protégée** (f)
- **cliché**, **attaché**, **pâté** (also has circumflex)
- **purée**, **risqué**, **passé**

### Grave (`)
- **crèche**, **crème** (e.g. crème brûlée, crème fraîche)
- **à la carte**, **à la mode**, **vis-à-vis**
- **pièce de résistance**

### Circumflex (^)
- **crêpe**
- **tête-à-tête**
- **raison d'être**
- **débâcle**, **pâté**, **bête noire**
- **maître d'**

### Cedilla (¸)
- **façade**, **garçon**, **soupçon**

## Spanish inventory

### Tilde (~) over n — `ñ` (U+00F1)
- **jalapeño**, **piña colada**, **piñata**, **piñon**
- **mañana**
- **niño**, **niña**
- **El Niño**, **La Niña** (climate phenomena)
- **señor**, **señora**, **señorita**
- **cañón** (when writing the Spanish form rather than the anglicized "canyon")
- **doña**, **don** (don has no tilde, listed for symmetry)

### Acute on vowels (less common in English loanwords but used)
- **café** (also French; same spelling)
- **canapé** (also French)

## What's out of scope

- **Other languages** beyond French and Spanish (über, doppelgänger, smörgåsbord) — user has not signaled a preference. If they come up, ask before applying.
- **Common-enough-anglicized** (cafe, role, fete, jalapeno, pinata) without the accent is widespread; user's flags on naïve and ñ-words imply the *with-accent* form is preferred, so default to that everywhere.
- **Place names and proper nouns** in their host-language form are out of scope (Berlin, Köln, Bogotá) — but climate terms like "El Niño" *are* in scope above.
- **Words where the accent has fully dropped in English** (e.g. "premier" not "premièr") — these are now English words, not loanwords.

Encoding is UTF-8 throughout the toolchain; all these characters render correctly in markdown, terminals, and the md-to-pdf pipeline.
