;; selftest.wat — smoke test for wasm3 parse / load / call / return.
;;
;; Deliberately pure-compute: returns i32 42 without touching any host
;; import. Runtime init runs this before any MailboxesManager actor is
;; populated, so host-import calls would assert. Host-import wiring is
;; covered by real level scripts (snowgoons director).
;;
;; Compile with: wat2wasm selftest.wat -o selftest.wasm
;; The committed selftest.wasm is ground truth; wf_game does NOT invoke
;; wat2wasm.

(module
  (func (export "main") (result i32)
    i32.const 42))
