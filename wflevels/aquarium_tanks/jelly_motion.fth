\ Simplified quick contraction, recovery and open-bell coast; not a fluid model.
: tk-ease dup dup * swap 2 * 3 swap - * ;
: tk-contract tk-frac dup tk-contract-fraction < if
  tk-contract-fraction / tk-ease
else dup tk-contract-fraction tk-recover-fraction + < if
  tk-contract-fraction - tk-recover-fraction / tk-ease 1 swap -
else drop 0 then then ;
