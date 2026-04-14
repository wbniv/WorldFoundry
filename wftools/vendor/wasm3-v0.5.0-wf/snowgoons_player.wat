;; snowgoons player — wasm reference implementation.
;; Forwards raw joystick state to the physics-input mailbox every tick.
;;
;; Not patched into snowgoons.iff by scripts/patch_snowgoons_wasm.py: the
;; player's script slot in the iff is 77 B, which can't hold even the
;; smallest base64-wrapped wasm module (header alone is ~80 B raw / ~108 B
;; base64). The demo iff therefore keeps Fennel (or Lua) for the player
;; and uses wasm only for the director. The committed snowgoons_player.wasm
;; still compiles and runs — drop it into a binary-chunk IFF (follow-up)
;; and it'll work.
;;
;; INDEXOF_HARDWARE_JOYSTICK1_RAW = 1009
;; INDEXOF_INPUT                  = 3024
(module
  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env" "write_mailbox" (func $write (param i32 f32)))
  (func (export "main")
    i32.const 3024
    i32.const 1009
    call $read
    call $write))
