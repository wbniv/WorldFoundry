;; snowgoons player — WAMR version.
;; Uses host-supplied global imports for INDEXOF_* constants instead of
;; baked literals.  WAMR resolves the (import "consts" …) globals from
;; AddConstantArray data at instantiation time.
;;
;; To compile:  wat2wasm snowgoons_player.wat -o snowgoons_player.wasm
;; Requires wabt (https://github.com/WebAssembly/wabt).
;;
;; Compiled: snowgoons_player.wasm (global-import version) is committed
;; alongside this file.  patch_snowgoons_wamr.py uses the director wasm;
;; the player wasm is available for future patching scripts.
(module
  (import "consts" "INDEXOF_HARDWARE_JOYSTICK1_RAW" (global $raw i32))
  (import "consts" "INDEXOF_INPUT"                  (global $inp i32))
  (import "env"    "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env"    "write_mailbox" (func $write (param i32 f32)))
  (func (export "main")
    global.get $inp
    global.get $raw
    call $read
    call $write))
