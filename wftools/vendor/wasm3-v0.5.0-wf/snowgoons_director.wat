;; snowgoons director — wasm reference implementation.
;; For each of mailboxes 100/99/98, if the value is non-zero, forward it to
;; INDEXOF_CAMSHOT. Mirrors the Lua/Fennel director exactly.
;;
;; INDEXOF_CAMSHOT = 1021
(module
  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env" "write_mailbox" (func $write (param i32 f32)))
  (func $maybe (param $mb i32)
    (local $v f32)
    local.get $mb
    call $read
    local.tee $v
    f32.const 0
    f32.ne
    if
      i32.const 1021
      local.get $v
      call $write
    end)
  (func (export "main")
    i32.const 100 call $maybe
    i32.const 99  call $maybe
    i32.const 98  call $maybe))
