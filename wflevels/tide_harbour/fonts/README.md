# Fonts for the Tide Harbour build

`NotoSansThai-Bold.ttf` is the static Noto Sans Thai Bold (Debian `fonts-noto-core`, SIL Open Font License 1.1; licence text in
`LICENSE-Noto.txt`). The build draws the panel's Thai digits and labels, and the dial's Thai numerals, from it.

Why bold and not the copy Blender ships: the build used to embolden Regular with the text curve's `offset`, and an offset curve
self-intersects on the thin loops of ๕ ๗ ๘, so Blender's fill tore them and the digits came out with bites missing (seen on cast1,
2026-11-22). A bold static font needs no offset, so Thai text is drawn with offset 0.
