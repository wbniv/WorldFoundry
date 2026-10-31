# Scene contract

The generator calls `read_factory_settings(use_empty=True)`, creates actors from
current OADs, seeds schema defaults and overrides baseline values explicitly.
The exported scene inventory includes every scalar property and actor purpose
collection. OAD defaults remain schema-owned; no imported level owns them.

`CORE` contains Level, Room, one Director, Player, Camera, two CamShots,
CameraOrigin, TargetFollow, TargetFirst, Directional, Ambient and Background.
The camera reference targets are stationary authoring reference points; the
runtime CamShots track Player. There is one room enclosing the entire floor
plus camera/fall-recovery margins. Room adjacency is absent.

`GROUND/Floor` uses one collision slab and one tiled top mesh. Its tile UVs stay
within 0…1. Four hundred 10 × 10 top quads carry the same 256² grid texture;
there are no individual grid-line actors or overlapping top surfaces.

`DEBUG_DEFAULT` contains OriginAxes, UnitCube, SpawnRuler and CoordinateLabels.
Only UnitCube is a StatPlat obstacle. Other references use anchored Platform
actors and do not become static world collision geometry. Text labels use
one 512 × 256 atlas and one mesh. Labels are exported, not viewport annotations.

`CONFIG` contains two Target actors, `FieldTypes` and `RuntimeSettings`, each carrying
its own supplemental property catalog: one field per touch-settings example, and the
Runtime Options, Level Memory and Level Behavior sheets. Both stand at (2, −4, 1), so
Pick in 3D shows them as one bracket with an "Objects here" list. Director is unique by
engine contract; these owners do not introduce extra Directors. The 118-field
descriptor gallery is a build-time test fixture, not an owner.

`TEAPOTS` contains eight Utah teapots (52, 240, 552, 992, 2 256, 4 032, 9 120 and 16 256
faces, from tessellation levels 1, 2, 3, 4, 6, 8, 12 and 16) and one `TeapotLabels` mesh of
standing face-count boards. All are anchored `Platform` actors with `Mass 0`, so they are
visual only. The collection is created after `CONFIG`, so the teapots take actor indices
21–29 after the two settings owners (19 and 20). Every preset includes them; read indices
from `actor-map.json`, never hard-code them.

`DIAGNOSTICS` contains box/wall, camera wall, three steps, three wedges and an
asymmetric UV swatch. All have an explicit export exclusion flag outside the
diagnostics preset. `AUTHORING_ONLY` contains the Blender inspection camera.

Player visual dimensions approximate the configured 0.6 × 0.6 × 1.8 envelope.
Orange bars show the authored collision AABB; they are not a claim that a Jolt
character uses a box. Existing Jolt character code derives a Z-up capsule with
radius 0.3 and cylinder half-height 0.6 from that AABB. Runtime grounding and
obstacle acceptance must confirm the resulting envelope. Static meshes can
use mesh collision through the existing backend; do not infer their actual
hull from the wedge's visual shape without inspecting the runtime receipt.
