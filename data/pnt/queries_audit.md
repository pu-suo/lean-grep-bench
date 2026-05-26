# Query Generation Audit

- Total queries: **2,740**
- By scenario:
  - mathlib_only: 2,207
  - local_only: 524
  - mixed: 9
- Query word count: 5th=6.0, 50th=10.0, 95th=15.0
- Leakage breakdown:
  - cited-name only: **127 (4.64%)**
  - goal-restatement only: **0 (0.00%)**
  - both:              **0 (0.00%)**
  - **any leakage:**   **127 (4.64%)**

## 15 random spot-checks

### 1. `pnt_step_01584.q1` — scenario: `local_only`

- **Ground truth**: `Smooth1LeOne`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/MellinCalculus.lean:1501`
- **Enclosing**: `Smooth1MellinConvergent`
- **Goal**: `⊢ Smooth1 Ψ ε x ≤ 1`
- **Hypotheses**:
  - `Ψ : ℝ → ℝ`
  - `ε : ℝ`
  - `diffΨ : ContDiff ℝ 1 Ψ`
  - `suppΨ : Function.support Ψ ⊆ Icc (1 / 2) 2`
  - `hε : ε ∈ Ioo 0 1`
  - `Ψnonneg : ∀ x > 0, 0 ≤ Ψ x`
  - … (+5 more)
- **Prior tactics**:
  - `rw [Asymptotics.isBigO_iff]`
  - `use 1`
  - `filter_upwards [eventually_mem_nhdsWithin] with x hx`
  - `simp only [norm_real, norm_eq_abs, neg_zero, rpow_zero, one_mem, CStarRing.norm_of_mem_unitary,
  mul_one]`
  - `rw [_root_.abs_of_nonneg <| Smooth1Nonneg Ψnonneg hx hε.1]`
- **Redacted line**: `exact ??? Ψnonneg mass_one hε.1 hx`
- **Query**: Integral of rescaled nonnegative kernel ≤ one

### 2. `pnt_step_01663.q1` — scenario: `mathlib_only`

- **Ground truth**: `Nat.lt_of_floor_lt`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/PrimeInInterval.lean:48`
- **Enclosing**: `HasPrimeInInterval.iff_pi_ge`
- **Goal**: `⊢ x < ↑p`
- **Hypotheses**:
  - `x h : ℝ`
  - `hpi : ↑⌊x + h⌋₊.primeCounting > ↑⌊x⌋₊.primeCounting`
  - `hnat : ⌊x⌋₊.primeCounting < ⌊x + h⌋₊.primeCounting := cast cast_lt._simp_1 hpi`
  - `p : ℕ`
  - `hpprime : Nat.Prime p`
  - `hp1 : ⌊x⌋₊ + 1 ≤ p`
  - … (+1 more)
- **Prior tactics**:
  - `obtain ⟨p, hpprime, hp1, hp2⟩ := prime_in_gap' ⌊x⌋₊ ⌊x + h⌋₊ hnat`
  - `refine ⟨p, hpprime, ?_, ?_⟩`
  - `· exact lt_of_floor_lt <| lt_of_lt_of_le (Nat.lt_succ_self ⌊x⌋₊) hp1`
  - `· have hp_floor : p ≤ ⌊x + h⌋₊ := Nat.lt_succ_iff.mp hp2
  have hfloor_pos : 0 < ⌊x + h⌋₊ := lt_of_lt_of_le hpprime.pos hp_floor
  have hxh_pos : 0 < x + h := Nat.pos_of_floor_pos hfloor_pos
  exact ( …`
  - `exact_mod_cast hpi`
- **Redacted line**: `exact ??? <| lt_of_lt_of_le (Nat.lt_succ_self ⌊x⌋₊) hp1`
- **Query**: floor(x) < n implies x < n (cast)

### 3. `pnt_step_00172.q1` — scenario: `local_only`

- **Ground truth**: `a2_43_mem_Icc`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/BKLNW_a2_bounds.lean:531`
- **Enclosing**: `cor_5_1_rem'`
- **Goal**: `⊢ (1 + 193571378 / 10 ^ 16) * max (f (rexp 43)) (f (2 ^ (⌊43 / log 2⌋₊ + 1))) ∈ Set.Icc 1.03252 (1.03252 + 1 / 10 ^ 5)`
- **Prior tactics**:
  - `rw [rpow_neg_nat]`
  - `exact a2_35_mem_Icc`
  - `rw [rpow_neg_nat]`
  - `exact a2_40_mem_Icc`
  - `rw [rpow_neg_nat]`
- **Redacted line**: `exact ???`
- **Query**: max of two elements in closed interval is in interval

### 4. `pnt_step_01067.q1` — scenario: `local_only`

- **Ground truth**: `riemannZeta_conj`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/MediumPNT.lean:110`
- **Enclosing**: `Chebyshev.smoothedChebyshevIntegrand_conj`
- **Goal**: `⊢ ζ ((starRingEnd ℂ) s) = (starRingEnd ℂ) (ζ s)`
- **Hypotheses**:
  - `SmoothingF : ℝ → ℝ`
  - `ε X : ℝ`
  - `Xpos : 0 < X`
  - `s : ℂ`
- **Prior tactics**:
  - `unfold SmoothedChebyshevIntegrand`
  - `simp only [map_mul, map_div₀, map_neg]`
  - `congr`
  - `· exact deriv_riemannZeta_conj s`
- **Redacted line**: `· exact ??? s`
- **Query**: complex conjugation commutes with the Riemann zeta function

### 5. `pnt_step_02101.q1` — scenario: `mathlib_only`

- **Ground truth**: `tsum_nonneg`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/Wiener.lean:2810`
- **Enclosing**: `limiting_fourier_variant_lim1`
- **Goal**: `⊢ 0 ≤ T σ`
- **Hypotheses**:
  - `f : ℕ → ℝ`
  - `x : ℝ`
  - `ψ : CS 2 ℂ`
  - `hpos : 0 ≤ f`
  - `hψpos : ∀ (y : ℝ), 0 ≤ (𝓕 ψ.toFun y).re ∧ (𝓕 ψ.toFun y).im = 0`
  - `S : ℝ → ℂ`
  - … (+106 more)
- **Prior tactics**:
  - `have hden : 0 < (n : ℝ) ^ σ := Real.rpow_pos_of_pos hnpos σ`
  - `have : 0 ≤ (f n) / ((n : ℝ) ^ σ) := div_nonneg hf (le_of_lt hden)`
  - `simp [rterm, hn, mul_nonneg this hw]`
  - `exact_mod_cast (Nat.pos_of_ne_zero hn)`
  - `intro σ`
- **Redacted line**: `exact ??? (fun n => rterm_nonneg σ n)`
- **Query**: infinite sum of nonnegative terms is nonnegative

### 6. `pnt_step_01997.q1` — scenario: `mathlib_only`

- **Ground truth**: `mul_le_mul_of_nonneg_right`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/Wiener.lean:1093`
- **Enclosing**: `limiting_fourier_lim3`
- **Goal**: `⊢ ‖G (↑u + ↑v * I)‖ * ‖ψ.toFun v‖ ≤ bound v`
- **Hypotheses**:
  - `x : ℝ`
  - `G : ℂ → ℂ`
  - `hG : ContinuousOn G {s | 1 ≤ s.re}`
  - `ψ : CS 2 ℂ`
  - `hx : 1 ≤ x`
  - `hh : ¬tsupport ψ.toFun = ∅`
  - … (+205 more)
- **Prior tactics**:
  - `have r2 := isMaxOn_iff.mp hmax _ r1`
  - `have r4 : (x : ℂ) ≠ 0 := by simp ; linarith`
  - `have r5 : arg x = 0 := by simp [arg_eq_zero_iff] ; linarith`
  - `have r3 : ‖(x : ℂ) ^ (v * I)‖ = 1 := by simp [norm_cpow_of_ne_zero r4, r5]`
  - `simp_rw [norm_mul, r3, mul_one]`
- **Redacted line**: `exact ??? r2 (norm_nonneg _)`
- **Query**: if a ≤ b and 0 ≤ c then a*c ≤ b*c

### 7. `pnt_step_01665.q1` — scenario: `mathlib_only`

- **Ground truth**: `le_trans`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/PrimeInInterval.lean:103`
- **Enclosing**: `HasPrimeInInterval.iff_theta_ge`
- **Goal**: `⊢ 0 ≤ x`
- **Hypotheses**:
  - `x h : ℝ`
  - `p : ℕ`
  - `hpprime : Nat.Prime p`
  - `hxp : x < ↑p`
  - `hpxh : ↑p ≤ x + h`
  - `s : Finset ℕ := filter Nat.Prime (Icc 0 ⌊x⌋₊)`
  - … (+49 more)
- **Prior tactics**:
  - `rw [mem_filter, mem_Icc] at hpins'`
  - `have hx_nn : 0 ≤ x := by
  have hfloor_pos : 0 < ⌊x⌋₊ := lt_of_lt_of_le hpprime.pos hpins'.1.2
  exact le_trans (by norm_num : (0 : ℝ) ≤ 1) (Nat.floor_pos.mp hfloor_pos)`
  - `exact (not_le_of_gt hxp) ((Nat.cast_le.2 hpins'.1.2).trans (Nat.floor_le hx_nn))`
  - `simpa [s] using hpins`
  - `have hfloor_pos : 0 < ⌊x⌋₊ := lt_of_lt_of_le hpprime.pos hpins'.1.2`
- **Redacted line**: `exact ??? (by norm_num : (0 : ℝ) ≤ 1) (Nat.floor_pos.mp hfloor_pos)`
- **Query**: transitivity of ≤: from a ≤ b and b ≤ c infer a ≤ c

### 8. `pnt_step_01219.q1` — scenario: `mathlib_only`

- **Ground truth**: `Filter.mem_inf_of_left`
- **Tactic kind**: `refine`
- **Source**: `PrimeNumberTheoremAnd/MediumPNT.lean:1717`
- **Enclosing**: `Chebyshev.integral_evaluation`
- **Goal**: `⊢ {x_1 | (‖↑x + ↑x_1 * I‖ ^ 2)⁻¹ ≤ (x_1 ^ 2)⁻¹} ∈ ae volume ⊓ 𝓟 (Iic (-T))`
- **Hypotheses**:
  - `x T : ℝ`
  - `T_large : 3 < T`
  - `T00 : ∀ (x t : ℝ), t ^ 2 ≤ ‖↑x + ↑t * I‖ ^ 2 :=`
  - `fun x t =>`
  - `Eq.mpr (id (congrArg (fun _a => t ^ 2 ≤ _a ^ 2) (norm_add_mul_I x t)))`
  - `(Eq.mpr`
  - … (+78 more)
- **Prior tactics**:
  - `positivity`
  - `positivity`
  - `unfold Filter.EventuallyLE`
  - `unfold Filter.Eventually`
  - `simp_all only [ne_eq, measurableSet_Iic, ae_restrict_eq]`
- **Redacted line**: `refine ??? ?_`
- **Query**: predicate true off a single point implies almost everywhere on interval

### 9. `pnt_step_01959.q1` — scenario: `local_only`

- **Ground truth**: `Finset.sum_shift_front`
- **Tactic kind**: `apply`
- **Source**: `PrimeNumberTheoremAnd/Wiener.lean:581`
- **Enclosing**: `Finset.sum_shift_front'`
- **Goal**: `⊢ shift (cumsum u) n = ((fun x => u 0) + cumsum (shift u)) n`
- **Hypotheses**:
  - `E : Type u_1`
  - `inst✝ : Ring E`
  - `u : ℕ → E`
  - `n : ℕ`
- **Prior tactics**:
  - `ext n`
- **Redacted line**: `apply ???`
- **Query**: shifted cumulative sum equals first term plus cumulative sum of shifted sequence

### 10. `pnt_step_01473.q1` — scenario: `mathlib_only`

- **Ground truth**: `DifferentiableOn.neg`
- **Tactic kind**: `apply`
- **Source**: `PrimeNumberTheoremAnd/MediumPNT.lean:4224`
- **Enclosing**: `Chebyshev.MediumPNT`
- **Goal**: `⊢ DifferentiableOn ℂ (fun s => -(ζ' s / ζ s)) (Icc σ₂ 2 ×ℂ Icc (-3) 3 \ {1})`
- **Hypotheses**:
  - `ν : ℝ → ℝ`
  - `ν_supp : support ν ⊆ Icc (1 / 2) 2`
  - `ContDiff1ν : ContDiff ℝ 1 ν :=`
  - `ContDiff.of_le _fvar.2150185 (of_eq_true (Eq.trans WithTop.one_le_coe._simp_2 le_top._simp_2))`
  - `ν_nonneg : ∀ x > 0, 0 ≤ ν x := fun x x_1 => @_fvar.2150186 x`
  - `ν_massOne : ∫ (x : ℝ) in Ioi 0, ν x / x = 1 :=`
  - … (+197 more)
- **Prior tactics**:
  - `· intro s hs
  apply DifferentiableAt.differentiableWithinAt
  apply DifferentiableAt.const_cpow (by fun_prop)
  left
  norm_cast
  linarith`
  - `apply DifferentiableOn.mul`
  - `· rw [(by ext; ring : (fun s ↦ -ζ' s / ζ s) = (fun s ↦ -(ζ' s / ζ s)))]
  apply DifferentiableOn.neg holo2`
  - `· intro s hs
  apply DifferentiableAt.differentiableWithinAt
  apply Smooth1MellinDifferentiable ContDiff1ν ν_supp ⟨ε_pos, ε_lt_one⟩ ν_nonneg ν_massOne
  linarith[mem_reProdIm.mp hs.1 |>.1.1]`
  - `rw [(by ext; ring : (fun s ↦ -ζ' s / ζ s) = (fun s ↦ -(ζ' s / ζ s)))]`
- **Redacted line**: `apply ??? holo2`
- **Query**: Holomorphic on implies complex differentiable on set

### 11. `pnt_step_02396.q1` — scenario: `mathlib_only`

- **Ground truth**: `add_le_of_nonpos_right`
- **Tactic kind**: `exact`
- **Source**: `PrimeNumberTheoremAnd/ZetaBounds.lean:957`
- **Enclosing**: `ZetaSum_aux1_3b`
- **Goal**: `⊢ 1 / 2 + (↑⌊x⌋ - x) ≤ 1 / 2`
- **Hypotheses**:
  - `x : ℝ`
- **Prior tactics**:
  - `ring_nf`
- **Redacted line**: `exact ??? <| sub_nonpos.mpr (Int.floor_le x)`
- **Query**: if a ≤ b then c + a ≤ c + b

### 12. `pnt_step_00901.q1` — scenario: `mathlib_only`

- **Ground truth**: `le_mul_of_one_le_right`
- **Tactic kind**: `refine`
- **Source**: `PrimeNumberTheoremAnd/Mathlib/Analysis/Asymptotics/Uniformly.lean:140`
- **Enclosing**: `ContinuousOn.const_isBigOWithUniformlyOn_isCompact_rev`
- **Goal**: `⊢ ‖c‖ ≤ ‖c‖ * (‖match x with | (i, _x) => C i‖ / sInf (norm '' (C '' s)))`
- **Hypotheses**:
  - `α : Type u_1`
  - `ι : Type u_2`
  - `E : Type u_3`
  - `F : Type u_4`
  - `s : Set ι`
  - `inst✝² : TopologicalSpace ι`
  - … (+13 more)
- **Prior tactics**:
  - `· rewrite [mul_comm_div]
  replace hs := hs.image_of_continuousOn hf |>.image continuous_norm
  have h_sInf := hs.isGLB_sInf <| Set.image_nonempty.mpr <| Set.image_nonempty.mpr ⟨x.1, hx.1⟩
  refine le …`
  - `exact prod_mem_prod (mem_principal_self s) univ_mem`
  - `rewrite [mul_comm_div]`
  - `replace hs := hs.image_of_continuousOn hf |>.image continuous_norm`
  - `have h_sInf := hs.isGLB_sInf <| Set.image_nonempty.mpr <| Set.image_nonempty.mpr ⟨x.1, hx.1⟩`
- **Redacted line**: `refine ??? (norm_nonneg c) <| (one_le_div ?_).mpr <|
  h_sInf.1 <| Set.mem_image_of_mem _ <| Set.mem_image_of_mem _ hx.1`
- **Query**: 1 ≤ a / b iff b ≤ a when b > 0

### 13. `pnt_step_02074.q1` — scenario: `mathlib_only`

- **Ground truth**: `tendsto_of_liminf_eq_limsup`
- **Tactic kind**: `refine`
- **Source**: `PrimeNumberTheoremAnd/Wiener.lean:2295`
- **Enclosing**: `WienerIkeharaInterval`
- **Goal**: `⊢ Tendsto (S Iab) atTop (𝓝 (A * (b - a)))`
- **Hypotheses**:
  - `A a b : ℝ`
  - `G : ℂ → ℂ`
  - `f : ℕ → ℝ`
  - `hpos : 0 ≤ f`
  - `hf : ∀ (σ' : ℝ), 1 < σ' → Summable (nterm (fun n => ↑(f n)) σ')`
  - `hcheby : cheby fun n => ↑(f n)`
  - … (+195 more)
- **Prior tactics**:
  - `have Iab0 : IsCoboundedUnder (· ≥ ·) atTop (S Iab) := Iab2.isCoboundedUnder_ge`
  - `have Iab1 : IsCoboundedUnder (· ≤ ·) atTop (S Iab) := Iab3.isCoboundedUnder_le`
  - `have sup_le : limsup (S Iab) atTop ≤ A * (b - a) := by
  have l_sup : ∀ᶠ ε in 𝓝[>] 0, limsup (S Iab) atTop ≤ A * (b - a + ε) := by
    filter_upwards [interval_approx_sup ha hb] with ε ⟨ψ, h1, h2, h3, …`
  - `have le_inf : A * (b - a) ≤ liminf (S Iab) atTop := by
  have l_inf : ∀ᶠ ε in 𝓝[>] 0, A * (b - a - ε) ≤ liminf (S Iab) atTop := by
    filter_upwards [interval_approx_inf ha hb] with ε ⟨ψ, h1, h2, h3, …`
  - `have : liminf (S Iab) atTop ≤ limsup (S Iab) atTop := liminf_le_limsup Iab2 Iab3`
- **Redacted line**: `refine ??? ?_ ?_ Iab2 Iab3 <;> linarith`
- **Query**: tendsto to constant iff limsup ≤ c and liminf ≥ c under boundedness
- ⚠ **Leakage**: cited-name leakage

### 14. `pnt_step_00577.q1` — scenario: `mathlib_only`

- **Ground truth**: `Filter.Tendsto.div_atTop`
- **Tactic kind**: `apply`
- **Source**: `PrimeNumberTheoremAnd/Consequences.lean:1535`
- **Enclosing**: `tendsto_by_squeeze`
- **Goal**: `⊢ Tendsto (fun x => log (1 + ε) / log ↑x) atTop (nhds 0)`
- **Hypotheses**:
  - `ε : ℝ`
  - `hε : ε > 0`
  - `c : ℝ → ℝ`
  - `pi_x_eq : ∀ (x : ℝ), ↑⌊x⌋₊.primeCounting = (1 + c x) * x / log x`
  - `hc : Tendsto (fun x => c x) atTop (nhds 0)`
  - `d : ℝ := ε / (2 * (2 + ε))`
  - … (+135 more)
- **Prior tactics**:
  - `conv =>
  arg 3
  equals nhds (1 + 0) => simp`
  - `apply Filter.Tendsto.add`
  - `· simp`
  - `· apply Filter.Tendsto.div_atTop (a := log (1 + ε))
  · simp
  · simp only [tendsto_comp_val_Ioi_atTop]
    exact tendsto_log_atTop`
  - `simp`
- **Redacted line**: `apply ??? (a := log (1 + ε))`
- **Query**: If f tends to +∞ then a / f tends to 0

### 15. `pnt_step_01161.q1` — scenario: `mathlib_only`

- **Ground truth**: `riemannZeta_ne_zero_of_one_lt_re`
- **Tactic kind**: `apply`
- **Source**: `PrimeNumberTheoremAnd/MediumPNT.lean:1134`
- **Enclosing**: `Chebyshev.SmoothedChebyshevPull1_aux_integrable`
- **Goal**: `⊢ ζ (↑σ₀ + ↑t * I) ≠ 0`
- **Hypotheses**:
  - `SmoothingF : ℝ → ℝ`
  - `ε : ℝ`
  - `ε_pos : 0 < ε`
  - `ε_lt_one : ε < 1`
  - `X : ℝ`
  - `X_gt : 3 < X`
  - … (+361 more)
- **Prior tactics**:
  - `exact this`
  - `have diffζ := differentiableAt_riemannZeta s_ne_one`
  - `apply ContinuousAt.div`
  - `· apply ContinuousAt.neg
  have : DifferentiableAt ℂ (fun s ↦ deriv riemannZeta s) s :=
    differentiableAt_deriv_riemannZeta s_ne_one
  convert realDiff_of_complexDiff (s := σ₀ + (t : ℂ) * I) this < …`
  - `· convert realDiff_of_complexDiff (s := σ₀ + (t : ℂ) * I) diffζ <;> simp`
- **Redacted line**: `· apply ???
  simp [σ₀_gt]`
- **Query**: Riemann zeta has no zeros for Re s > 1

