(module
 (import "env" "read_mailbox" (func $read (param i32) (result f32)))
 (import "env" "write_mailbox" (func $write (param i32 f32)))
 (import "consts" "INDEXOF_FRAMERATE" (global $fps i32))
 (func (export "main")
  (call $write (i32.const 1899) (call $read (global.get $fps)))))
