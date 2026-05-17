# Licences of vendored upstream packages

Each `.deb` we repackage and redistribute via this repo keeps the upstream's licence. Below is the running summary. The full text of each licence ships inside the corresponding `.deb` under `/usr/share/doc/<package>/copyright`.

| Package | Upstream | Licence | Where the text lives in the .deb |
|---|---|---|---|
| `task` | [go-task/task](https://github.com/go-task/task) | [MIT](https://github.com/go-task/task/blob/main/LICENSE) | `/usr/share/doc/task/copyright` |

## Planned future entries (not yet shipped)

| Package | Upstream | Licence | Notes |
|---|---|---|---|
| `ghidra` | [NSA / Ghidra](https://ghidra-sre.org/) | [Apache-2.0](https://github.com/NationalSecurityAgency/ghidra/blob/master/LICENSE) | Big tarball (~400 MB); host on R2. |
| `f9dasm` | [F9DASM](http://www.df.lth.se.orbin.se/~triad/f9dasm/) | [GPL-2.0](http://www.df.lth.se.orbin.se/~triad/f9dasm/f9dasm.html) | Compiles from source — small. |
| `vgmstream` | [vgmstream/vgmstream](https://github.com/vgmstream/vgmstream) | [ISC](https://github.com/vgmstream/vgmstream/blob/master/COPYING) | Audio decode for legacy formats. |
| `libvgm` | [ValleyBell/libvgm](https://github.com/ValleyBell/libvgm) | [GPL-2.0+](https://github.com/ValleyBell/libvgm/blob/master/LICENSE) | Sound chip emulation library. |
| `xa65` | [André Fachat](https://www.floodgap.com/retrotech/xa/) | [GPL-2.0+](https://www.floodgap.com/retrotech/xa/) | 6502 cross-assembler. |

## Foundry-authored content

- Metapackage control files (`packages/*/DEBIAN/control`)
- Helper scripts (`scripts/*.sh`)
- aptly config + GitHub Actions workflows

All [GPL-2.0](LICENSE), matching the World Foundry engine.
