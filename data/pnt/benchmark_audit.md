# Benchmark Verification Audit

- Accepted: **1,885** / 2,740 (68.80%)
- Rejected: 855
- By scenario:
  - mathlib_only: 1,476/2,207 (66.9%)
  - local_only: 402/524 (76.7%)
  - mixed: 7/9 (77.8%)

## 10 random rejections

### R1. `pnt_step_01369.q1` — scenario: `mathlib_only`

- **Query**: difference of functions continuous on a set is continuous on
- **Ground truth**: `ContinuousOn.sub` (mathlib)
- **Verifier reason**: The query asks about subtraction, but the declaration proves continuity of a quotient, not a difference.

### R2. `pnt_step_02510.q1` — scenario: `local_only`

- **Query**: Euclidean norm of 1 - (σ + i t) is at least |t|
- **Ground truth**: `le_trans₄` (local:pnt)
- **Verifier reason**: This is a generic transitivity lemma for ≤, not about complex norms or the inequality involving 1 - (σ + i t).

### R3. `pnt_step_01477.q1` — scenario: `mathlib_only`

- **Query**: map z ↦ z^r differentiable at nonzero points
- **Ground truth**: `DifferentiableAt.const_cpow` (mathlib)
- **Verifier reason**: The theorem treats differentiability of x ↦ c^f(x) (constant base, variable exponent), while the query asks about z ↦ z^r (variable base, constant exponent).

### R4. `pnt_step_00134.q1` — scenario: `local_only`

- **Query**: multiplying inequality by a nonnegative scalar preserves order
- **Ground truth**: `a2_150_exp_upper` (local:pnt)
- **Verifier reason**: This is a specific numeric inequality, not a general lemma about order preservation under multiplication by a nonnegative scalar.

### R5. `pnt_step_00914.q1` — scenario: `mathlib_only`

- **Query**: ceiling of a real ≤ floor of it plus one
- **Ground truth**: `trans` (mathlib)
- **Verifier reason**: The query is about a ceiling/floor inequality, but the declaration composes AddConstEquivs and is unrelated.

### R6. `pnt_step_01730.q1` — scenario: `local_only`

- **Query**: If A ⊆ B and p ∉ A then A ⊆ B \ {p}
- **Ground truth**: `rectangle_subset_punctured_rect` (local:pnt)
- **Verifier reason**: The lemma is a specialized rectangle case, while the query asks for a general set-theoretic result.

### R7. `pnt_step_01617.q1` — scenario: `mathlib_only`

- **Query**: square root strictly increasing on nonnegative reals
- **Ground truth**: `Filter.EventuallyLE.trans_eq` (mathlib)
- **Verifier reason**: It concerns eventual order relations in filters, not the monotonicity of the square root on nonnegative reals.

### R8. `pnt_step_01326.q1` — scenario: `mathlib_only`

- **Query**: 1 < x^n ↔ 1 < x for nonnegative x and n > 0
- **Ground truth**: `FirstOrder.Language.Theory.Iff.mpr` (mathlib)
- **Verifier reason**: This is a logic theorem about turning an equivalence into an implication, not about inequalities or powers of real numbers.

### R9. `pnt_step_02591.q1` — scenario: `mathlib_only`

- **Query**: continuous_on of composition on image of set
- **Ground truth**: `HasDerivAt.continuousOn` (mathlib)
- **Verifier reason**: It gives continuity from differentiability, not continuity of a composition on the image of a set.

### R10. `pnt_step_02733.q1` — scenario: `mathlib_only`

- **Query**: infimum equals element when that element is minimal in the set
- **Ground truth**: `le_antisymm` (mathlib)
- **Verifier reason**: This is a general antisymmetry lemma for ≤, not a result about infimums or minimal elements in a set.

## 10 random acceptances

### A1. `lgb_pnt_fda8a0a34bbcb714` — scenario: `mathlib_only`

- **Query**: L-series of arithmetic zeta function equals Riemann zeta for Re(s) > 1
- **Ground truth**: `ArithmeticFunction.LSeries_zeta_eq_riemannZeta` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/IwaniecKowalskiCh1.lean:246` (exact)
- **Enclosing**: `ArithmeticFunction.LSeries_d_eq_riemannZeta_pow`
- **Goal**: `⊢ L (fun n => ↑ζ n) s = riemannZeta s`

### A2. `lgb_pnt_2a7698d9ea98af22` — scenario: `mathlib_only`

- **Query**: if a < b and b < c then a < c
- **Ground truth**: `lt_trans` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/MediumPNT.lean:3305` (exact)
- **Enclosing**: `Chebyshev.I4Bound`
- **Goal**: `⊢ 1 / (2 * π) < 1`

### A3. `lgb_pnt_1b52239fa107438a` — scenario: `mathlib_only`

- **Query**: product of a number's prime factors divides the number
- **Ground truth**: `Nat.prod_primeFactors_dvd` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/Mathlib/NumberTheory/Sieve/SelbergBounds.lean:413` (exact)
- **Enclosing**: `Sieve.CompletelyMultiplicative.selbergBoundingSum_ge_sum_div`
- **Goal**: `⊢ ∏ p ∈ m.primeFactors, p ∣ m`

### A4. `lgb_pnt_542c57bea3cd4771` — scenario: `mathlib_only`

- **Query**: partial summation expressing π(x) via θ(x) for x≥2
- **Ground truth**: `Chebyshev.primeCounting_eq_theta_div_log_add_integral` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/Ramanujan.lean:167` (exact)
- **Enclosing**: `Ramanujan.pi_error_identity`
- **Goal**: `⊢ _root_.pi x = θ x / log x + ∫ (x : ℝ) in 2..x, θ x / (x * log x ^ 2)`

### A5. `lgb_pnt_6d8dcec809ec428c` — scenario: `mathlib_only`

- **Query**: Positive c and |t| > 3 imply c/(log |t|)^7 > 0
- **Ground truth**: `div_pos` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/ZetaBounds.lean:3169` (apply)
- **Enclosing**: `ZetaZeroFree`
- **Goal**: `⊢ 0 < c / Real.log |t| ^ 7`

### A6. `lgb_pnt_990fbf85fd66869a` — scenario: `mathlib_only`

- **Query**: transitivity of set inclusion: if A⊆B and B⊆C then A⊆C
- **Ground truth**: `subset_trans` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/ZetaBounds.lean:3605` (exact)
- **Enclosing**: `triv_bound_zeta`
- **Goal**: `⊢ Metric.eball 1 1 ⊆ U`

### A7. `lgb_pnt_290964474887705f` — scenario: `mathlib_only`

- **Query**: if a divides b and b divides c then a divides c
- **Ground truth**: `dvd_trans` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/Consequences.lean:1996` (exact)
- **Enclosing**: `lambda_eq_sum_sq_dvd_mu`
- **Goal**: `⊢ d1 ^ 2 ∣ m * n`

### A8. `lgb_pnt_13e08757e889e898` — scenario: `mathlib_only`

- **Query**: Complex number with positive real part is nonzero
- **Ground truth**: `Complex.ne_zero_of_re_pos` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/MediumPNT.lean:3445` (refine)
- **Enclosing**: `Chebyshev.I4Bound`
- **Goal**: `⊢ ↑X ≠ 0`

### A9. `lgb_pnt_0adc411a84910c31` — scenario: `mathlib_only`

- **Query**: cast of floor of a nonnegative real is at most the real
- **Ground truth**: `Nat.floor_le` (mathlib)
- **Provenance**: `PrimeNumberTheoremAnd/BrunTitchmarsh.lean:94` (apply)
- **Enclosing**: `BrunTitchmarsh.primesBetween_le_siftedSum_add`
- **Goal**: `⊢ ↑⌊z⌋₊ ≤ z`

### A10. `lgb_pnt_52787ed7c0c160dd` — scenario: `local_only`

- **Query**: upper bound for Chebyshev psi assuming 100 ≤ y ≤ 1e19
- **Ground truth**: `FKS2.psi_le_bound_medium` (local:pnt)
- **Provenance**: `PrimeNumberTheoremAnd/FKS2.lean:1004` (exact)
- **Enclosing**: `FKS2.psi_le_bound`
- **Goal**: `⊢ ψ y ≤ 1.00000002 * y + 0.94 * y ^ (1 / 2)`

