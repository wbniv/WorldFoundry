# Rebuild and verify the filesys level

The checked-in `wflevels/filesys/filesys.lev`, its mesh IFFs and the object schemas are the source inputs for the binary level. The build requires Git, Bash, Python 3, a Rust toolchain with Cargo, and access to the crates recorded in the three Rust `Cargo.lock` files (or a populated Cargo cache). No prebuilt compiler binaries are needed.

From a checkout, run:

```sh
scripts/check-filesys-rebuild.sh
# Or verify a specific committed revision:
scripts/check-filesys-rebuild.sh <git-revision>
```

The check exports only tracked inputs from that revision to a temporary directory, builds `iffcomp`, `levcomp` and `textile` with their locked dependencies, generates the level, and compares the complete `.lvl`, `.iff` and `-standalone.iff` byte for byte with that revision. It does not modify the checkout. An uncached machine needs network access to download Cargo dependencies.

This starts from the committed `.lev` and mesh exports; it does not rebuild those authoring assets from Blender. A matching result is specific to the checked revision and toolchain. If another machine differs, preserve the generated outputs, Cargo and Rust versions, and diagnostics before deciding whether the difference is a toolchain issue or stale inputs.
