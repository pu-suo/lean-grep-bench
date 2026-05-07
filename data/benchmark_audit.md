# Benchmark Verification Audit

- Accepted: **637** / 940 (67.77%)
- Rejected: 303
- By scenario:
  - mathlib_only: 339/587 (57.8%)
  - local_only: 283/336 (84.2%)
  - mixed: 15/17 (88.2%)

## 10 random rejections

### R1. `pfr_step_v2_00617.q1` — scenario: `mathlib_only`

- **Query**: pointwise inequality implies inequality of finite sums
- **Ground truth**: `Finset.sum_le_sum` (mathlib)
- **Verifier reason**: The declaration proves a product inequality, while the query asks about sums.

### R2. `pfr_step_v2_00652.q1` — scenario: `mathlib_only`

- **Query**: sum of coordinate projections is measurable
- **Ground truth**: `Finset.measurable_sum` (mathlib)
- **Verifier reason**: The lemma proves measurability of a finite product, not a sum of functions or coordinate projections.

### R3. `pfr_step_v2_00066.q1` — scenario: `mathlib_only`

- **Query**: Identically distributed preserved under composition with second projection
- **Ground truth**: `ProbabilityTheory.IdentDistrib.trans` (mathlib)
- **Verifier reason**: This is transitivity of IdentDistrib, not about composition with a second projection function.

### R4. `pfr_step_v2_00432.q1` — scenario: `mathlib_only`

- **Query**: preimages of distinct singletons under a function are disjoint
- **Ground truth**: `Disjoint.inter_right'` (mathlib)
- **Verifier reason**: It concerns disjointness under intersection, not preimages of singletons or functions.

### R5. `pfr_step_v2_00773.q1` — scenario: `mathlib_only`

- **Query**: measure of finite disjoint union equals sum of measures
- **Ground truth**: `lt_of_le_of_ne` (mathlib)
- **Verifier reason**: The lemma is about strict inequality from ≤ and ≠, not about measures or disjoint unions.

### R6. `pfr_step_v2_00741.q1` — scenario: `mathlib_only`

- **Query**: any set is contained in the universal set
- **Ground truth**: `Finset.filter_subset` (mathlib)
- **Verifier reason**: It states that filtering a finset yields a subset of it, not that any set is a subset of the universal set.

### R7. `pfr_step_v2_00616.q1` — scenario: `mathlib_only`

- **Query**: sum over off-diagonal pairs with value depending on first equals (m-1) times sum
- **Ground truth**: `Finset.sum_congr` (mathlib)
- **Verifier reason**: The query asks for an off-diagonal sum identity, while this theorem is just a congruence lemma equating sums over equal sets/functions.

### R8. `pfr_step_v2_00502.q1` — scenario: `mathlib_only`

- **Query**: intersection over proofs equals if p then s h else univ
- **Ground truth**: `Set.iInter_congr` (mathlib)
- **Verifier reason**: The lemma is a generic congruence for intersections, not the Prop-indexed if-then-else/univ behavior the query describes.

### R9. `pfr_step_v2_00721.q1` — scenario: `mathlib_only`

- **Query**: sum over finite index set invariant under permutation
- **Ground truth**: `Fintype.sum_equiv` (mathlib)
- **Verifier reason**: This lemma gives invariance of a finite product under an equivalence, while the query asks about sums.

### R10. `pfr_step_v2_00566.q1` — scenario: `mathlib_only`

- **Query**: sum over finite set is zero if each summand is zero
- **Ground truth**: `Finset.sum_eq_zero` (mathlib)
- **Verifier reason**: The declaration is about a product equaling 1 if each factor is 1, not a sum equaling 0 if each summand is 0.

## 10 random acceptances

### A1. `pfr_step_v2_00893.q1` — scenario: `mathlib_only`

- **Query**: measurable of pair from two measurable functions
- **Ground truth**: `Measurable.prod` (mathlib)
- **Provenance**: `PFR/WeakPFR.lean:141` (exact)
- **Enclosing**: `torsion_free_doubling`
- **Goal**: `⊢ Measurable (⟨Y'₁, ⟨Y'₂, X'⟩⟩)`

### A2. `pfr_step_v2_00332.q1` — scenario: `mathlib_only`

- **Query**: subset of a finite set is finite
- **Ground truth**: `Set.Finite.subset` (mathlib)
- **Provenance**: `PFR/ForMathlib/FiniteRange/Defs.lean:26` (apply)
- **Enclosing**: `finiteRange_of_finset`
- **Goal**: `⊢ (Set.range f).Finite`

### A3. `pfr_step_v2_00788.q1` — scenario: `local_only`

- **Query**: coordinate projections are independent for a product measure
- **Ground truth**: `ProbabilityTheory.indepFun_fst_snd` (pfr)
- **Provenance**: `PFR/RhoFunctional.lean:794` (exact)
- **Enclosing**: `rhoMinus_of_sum`
- **Goal**: `⊢ IndepFun Prod.fst Prod.snd (μ'.prod (uniformOn ↑A))`

### A4. `pfr_step_v2_00213.q1` — scenario: `mixed`

- **Query**: finite support of kernel preserved under left product with extra coordinate
- **Ground truth**: `ProbabilityTheory.Kernel.FiniteKernelSupport.prodMkLeft` (pfr)
- **Provenance**: `PFR/ForMathlib/Entropy/Kernel/RuzsaDist.lean:365` (apply)
- **Enclosing**: `ProbabilityTheory.Kernel.rdist_triangle`
- **Goal**: `⊢ (prodMkLeft (T × T'') η).FiniteKernelSupport`

### A5. `pfr_step_v2_00421.q1` — scenario: `mathlib_only`

- **Query**: cardinality of a finite set is monotone under inclusion
- **Ground truth**: `Nat.card_mono` (mathlib)
- **Provenance**: `PFR/ImprovedPFR.lean:964` (exact)
- **Enclosing**: `PFR_conjecture_improv_aux`
- **Goal**: `⊢ Nat.card ↑(A + A ∩ (↑H + {x₀})) ≤ Nat.card ↑(A + A)`

### A6. `pfr_step_v2_00211.q1` — scenario: `mixed`

- **Query**: finite kernel support preserved by left-product lifting of kernel
- **Ground truth**: `ProbabilityTheory.Kernel.FiniteKernelSupport.prodMkLeft` (pfr)
- **Provenance**: `PFR/ForMathlib/Entropy/Kernel/RuzsaDist.lean:365` (apply)
- **Enclosing**: `ProbabilityTheory.Kernel.rdist_triangle`
- **Goal**: `⊢ (prodMkLeft (T × T'') η).FiniteKernelSupport`

### A7. `pfr_step_v2_00140.q1` — scenario: `mathlib_only`

- **Query**: mutual independence implies coordinate independent of finset product
- **Ground truth**: `ProbabilityTheory.iIndepFun.indepFun_finset_prod_of_notMem` (mathlib)
- **Provenance**: `PFR/ForMathlib/Entropy/Group.lean:263` (exact)
- **Enclosing**: `ProbabilityTheory.max_entropy_le_entropy_prod`
- **Goal**: `⊢ IndepFun (X j) (∏ i ∈ s, X i) μ`

### A8. `pfr_step_v2_00935.q1` — scenario: `mathlib_only`

- **Query**: log is monotone on positive real numbers
- **Ground truth**: `Real.log_le_log` (mathlib)
- **Provenance**: `PFR/WeakPFR.lean:1067` (apply)
- **Enclosing**: `weak_PFR`
- **Goal**: `⊢ log (↑(Nat.card ↑A) * ↑(Nat.card ↑A) / (↑(Nat.card ↑B) * ↑(Nat.card ↑B))) ≤ log (↑(Nat.card ↑A) * ↑(Nat.card ↑A) / (↑(Nat.card ↑A') * ↑(Nat.card ↑A'')))`

### A9. `pfr_step_v2_00376.q1` — scenario: `mathlib_only`

- **Query**: if a ≤ b and b ≤ a then a = b
- **Ground truth**: `le_antisymm` (mathlib)
- **Provenance**: `PFR/HundredPercent.lean:166` (apply)
- **Enclosing**: `exists_isUniform_of_rdist_eq_zero`
- **Goal**: `⊢ d[X # X] = 0`

### A10. `pfr_step_v2_00832.q1` — scenario: `local_only`

- **Query**: rho of sum bounded by average of rhos and d when independent
- **Ground truth**: `rho_of_sum_le` (pfr)
- **Provenance**: `PFR/RhoFunctional.lean:1636` (exact)
- **Enclosing**: `new_gen_ineq_aux2`
- **Goal**: `⊢ ρ[Y₁ + Y₂ ; ℙ[|⟨T₂, T₂'⟩ ⁻¹' {w}] # A] ≤ (ρ[Y₁ ; ℙ[|⟨T₂, T₂'⟩ ⁻¹' {w}] # A] + ρ[Y₂ ; ℙ[|⟨T₂, T₂'⟩ ⁻¹' {w}] # A] + d[Y₁ ; ℙ[|⟨T₂, T₂'⟩ ⁻¹' {w}] # Y₂ ; ℙ[|⟨T₂, T₂'⟩ ⁻¹' {w}]]) / 2`

