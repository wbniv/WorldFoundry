# Rainbow goby — portrait A3

Open [poster.html](poster.html); print [rainbow-goby-biomechanics-a3.pdf](rainbow-goby-biomechanics-a3.pdf). The PDF is one
297 × 420 mm page. [poster.png](poster.png) is the preview.

The original vector drawings and text follow the existing aquarium research
posters. Sources are linked on the poster and in
[the separate research document](../rainbow-goby-research.md). The subject is an
adult male *Stiphodon ornatus*. Proposed controls and animation are labelled as
game choices, rather than measured animal kinematics.

Regenerate from the repository root:

```sh
python3 docs/reference/rainbow-goby-biomechanics-poster/make_poster.py
python3 docs/reference/rainbow-goby-biomechanics-poster/export_poster.py
```

Export requires Python Playwright with Chromium. `layout-review.json` records
the page dimensions and checks for document overflow; the rendered preview was
also inspected visually. The five SVG diagrams remain editable source assets.
