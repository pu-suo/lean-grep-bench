/-!
# Sample Lean file for parser testing
-/

namespace Foo.Bar

/-- The classic identity lemma. -/
theorem id_thm (x : Nat) : x = x := rfl

@[simp]
lemma succ_lemma (n : Nat) :
    n + 1 = Nat.succ n := by
  rfl

def double (n : Nat) : Nat :=
  n + n

structure Point where
  x : Nat
  y : Nat

@[reducible, inline]
instance : Inhabited Point :=
  ⟨{ x := 0, y := 0 }⟩

end Foo.Bar
