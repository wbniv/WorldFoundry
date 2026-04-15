;; snowgoons director — WAMR version.
;; Uses host-supplied global imports for INDEXOF_* constants instead of
;; baked literals.  WAMR resolves the (import "consts" …) globals from
;; AddConstantArray data at instantiation time.
;;
;; To compile:  wat2wasm snowgoons_director.wat -o snowgoons_director.wasm
;; Requires wabt (https://github.com/WebAssembly/wabt).
;;
;; Compiled: snowgoons_director.wasm (global-import version) is committed
;; alongside this file.  patch_snowgoons_wamr.py prefers it over the
;; wasm3-v0.5.0-wf baked-literal fallback.
(module
  (import "consts" "INDEXOF_CAMSHOT" (global $cam i32))
  (import "env"    "read_mailbox"    (func $read  (param i32) (result f32)))
  (import "env"    "write_mailbox"   (func $write (param i32 f32)))
  (func $maybe (param $mb i32)
    (local $v f32)
    local.get $mb
    call $read
    local.tee $v
    f32.const 0
    f32.ne
    if
      global.get $cam
      local.get $v
      call $write
    end)
  (func (export "main")
    i32.const 100 call $maybe
    i32.const 99  call $maybe
    i32.const 98  call $maybe))
