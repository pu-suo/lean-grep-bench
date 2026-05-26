# Query Generation Audit

- Total queries: **940**
- By scenario:
  - mathlib_only: 587
  - local_only: 336
  - mixed: 17
- Query word count: 5th=6.0, 50th=9.0, 95th=13.0
- Leakage breakdown:
  - cited-name only: **84 (8.94%)**
  - goal-restatement only: **0 (0.00%)**
  - both:              **0 (0.00%)**
  - **any leakage:**   **84 (8.94%)**

## 15 random spot-checks

### 1. `pfr_step_v2_00868.q1` — scenario: `mathlib_only`

- **Ground truth**: `Finset.sum_le_sum`
- **Tactic kind**: `apply`
- **Source**: `PFR/TauFunctional.lean:233`
- **Enclosing**: `condRuzsaDistance_ge_of_min`
- **Goal**: `⊢ ∑ x ∈ FiniteRange.toFinset W, (ℙ.real (W ⁻¹' {x}) * (ℙ.real (Z ⁻¹' {z}) * d[X₁ # X₂] - p.η * (ℙ.real (Z ⁻¹' {z}) * d[p.X₀₁ ; ℙ # X₁' ; ℙ[|Z ⁻¹' {z}]] - ℙ.real (Z ⁻¹' {z}) * d[p.X₀₁ # X₁])) - ℙ.real (Z ⁻¹' {z}) * (p.η * …`
- **Hypotheses**:
  - `Ω₀₁ : Type u_1`
  - `Ω₀₂ : Type u_2`
  - `inst✝¹⁴ : MeasureSpace Ω₀₁`
  - `inst✝¹³ : MeasureSpace Ω₀₂`
  - `G : Type uG`
  - `inst✝¹² : AddCommGroup G`
  - … (+34 more)
- **Prior tactics**:
  - `have hw (a : ℝ) : a = ∑ w ∈ FiniteRange.toFinset W, Measure.real ℙ (W ⁻¹' {w}) * a := by
  simp_rw [← Finset.sum_mul, ← map_measureReal_apply hW (MeasurableSet.singleton _),
    sum_measureReal_single …`
  - `rw [condRuzsaDist_eq_sum h1 hZ h2 hW, condRuzsaDist'_eq_sum h1 hZ, hz d[X₁ # X₂],
  hz d[p.X₀₁ # X₁], hz (p.η * (d[p.X₀₂ # X₂' | W] - d[p.X₀₂ # X₂])),
  ← Finset.sum_sub_distrib, Finset.mul_sum, ← Fin …`
  - `apply Finset.sum_le_sum`
  - `intro z _`
  - `rw [condRuzsaDist'_eq_sum h2 hW, hw d[p.X₀₂ # X₂],
  hw (Measure.real ℙ (Z ⁻¹' {z}) * d[X₁ # X₂] - p.η * (Measure.real ℙ (Z ⁻¹' {z}) *
    d[p.X₀₁ ; ℙ # X₁' ; ℙ[|Z ← z]] - Measure.real ℙ (Z ⁻¹' {z}) * …`
- **Redacted line**: `apply ???`
- **Query**: pointwise inequality on finset implies inequality of sums

### 2. `pfr_step_v2_00384.q1` — scenario: `mathlib_only`

- **Ground truth**: `MeasureTheory.integral_mono_ae`
- **Tactic kind**: `refine`
- **Source**: `PFR/ImprovedPFR.lean:368`
- **Enclosing**: `construct_good_prelim'`
- **Goal**: `⊢ ∫ (x : G), (fun x => k) x ∂Measure.map T₃ ℙ ≤ sum4`
- **Hypotheses**:
  - `G : Type u_1`
  - `inst✝⁸ : AddCommGroup G`
  - `inst✝⁷ : Fintype G`
  - `hG : MeasurableSpace G`
  - `inst✝⁶ : MeasurableSingletonClass G`
  - `inst✝⁵ : Module (ZMod 2) G`
  - … (+27 more)
- **Prior tactics**:
  - `have : sum4 = sum1 + p.η * (sum2 + sum3) := by
  simp only [sum1, sum2, sum3, sum4, integral_add .of_finite .of_finite, integral_const_mul]`
  - `rw [this, h2, h3, add_assoc, mul_add]`
  - `linarith`
  - `simp only [sum1, sum2, sum3, sum4, integral_add .of_finite .of_finite, integral_const_mul]`
  - `suffices (Measure.map T₃ ℙ)[fun _ ↦ k] ≤ sum4 by simpa using this`
- **Redacted line**: `refine ??? .of_finite .of_finite $
  ae_iff_of_countable.2 fun t ht ↦ ?_`
- **Query**: integral monotonicity via pointwise inequality on countable support

### 3. `pfr_step_v2_00768.q1` — scenario: `local_only`

- **Ground truth**: `Real.sum_mul_log_div_leq`
- **Tactic kind**: `apply`
- **Source**: `PFR/RhoFunctional.lean:478`
- **Enclosing**: `le_rhoMinus_of_subgroup`
- **Goal**: `⊢ (∑ h ∈ H', 1 / ↑(Nat.card ↥H)) * log ((∑ h ∈ H', 1 / ↑(Nat.card ↥H)) / ∑ h ∈ H', (Measure.map (T + UA) ℙ).real {h}) ≤ ∑ h ∈ H', 1 / ↑(Nat.card ↥H) * log (1 / ↑(Nat.card ↥H) / (Measure.map (T + UA) ℙ).real {h})`
- **Hypotheses**:
  - `G : Type uG`
  - `inst✝⁴ : AddCommGroup G`
  - `inst✝³ : Fintype G`
  - `hGm : MeasurableSpace G`
  - `inst✝² : DiscreteMeasurableSpace G`
  - `Ω : Type u_1`
  - … (+27 more)
- **Prior tactics**:
  - `· simp`
  - `· simpa [H'] using hH`
  - `simp`
  - `simpa [H'] using hH`
  - `rw [I₁]`
- **Redacted line**: `apply ??? (by simp) (by simp) (fun i hi h'i ↦ ?_)`
- **Query**: log-sum inequality for finite nonnegative sequences

### 4. `pfr_step_v2_00912.q1` — scenario: `mathlib_only`

- **Ground truth**: `Set.mem_inter`
- **Tactic kind**: `exact`
- **Source**: `PFR/WeakPFR.lean:468`
- **Enclosing**: `single_fibres`
- **Goal**: `⊢ UB ω ∈ B_ ↑y`
- **Hypotheses**:
  - `G : Type u_1`
  - `H : Type u_2`
  - `Ω : Type u_3`
  - `Ω' : Type u_4`
  - `inst✝¹³ : AddCommGroup G`
  - `inst✝¹² : Countable G`
  - … (+38 more)
- **Prior tactics**:
  - `obtain ⟨ω, hω⟩ := (FiniteRange.mem_iff _ _).mp x.property`
  - `use UA ω`
  - `exact Set.mem_inter (hUA_mem ω) hω`
  - `obtain ⟨ω, hω⟩ := (FiniteRange.mem_iff _ _).mp y.property`
  - `use UB ω`
- **Redacted line**: `exact ??? (hUB_mem ω) hω`
- **Query**: membership and image equality imply membership in set ∩ preimage singleton

### 5. `pfr_step_v2_00432.q1` — scenario: `mathlib_only`

- **Ground truth**: `Disjoint.inter_right'`
- **Tactic kind**: `apply`
- **Source**: `PFR/Kullback.lean:220`
- **Enclosing**: `ProbabilityTheory.IndepFun.map_add_eq_sum`
- **Goal**: `⊢ Disjoint (Z ⁻¹' {i}) (X ⁻¹' ((fun x => j + x) ⁻¹' S) ∩ Z ⁻¹' {j})`
- **Hypotheses**:
  - `Ω : Type u_1`
  - `G : Type u_5`
  - `mΩ : MeasurableSpace Ω`
  - `μ : Measure Ω`
  - `hG : MeasurableSpace G`
  - `inst✝² : Fintype G`
  - … (+10 more)
- **Prior tactics**:
  - `simp only [singleton_add, image_add_left, neg_neg, mem_inter_iff, mem_preimage,
  mem_singleton_iff] at hy`
  - `simp [hy.1, hy.2, add_comm]`
  - `intro i j hij`
  - `simp [Function.onFun]`
  - `apply Disjoint.inter_left'`
- **Redacted line**: `apply ???`
- **Query**: preimages of distinct singletons under a function are disjoint

### 6. `pfr_step_v2_00043.q1` — scenario: `mathlib_only`

- **Ground truth**: `ProbabilityTheory.IdentDistrib.trans`
- **Tactic kind**: `exact`
- **Source**: `PFR/ForMathlib/ConditionalIndependence.lean:261`
- **Enclosing**: `ProbabilityTheory.condIndep_copies`
- **Goal**: `⊢ IdentDistrib (fun a => ((Prod.snd ∘ Prod.fst) a, a.2)) (fun a => (X a, Y a)) (m y) μ[|Y ⁻¹' {y}]`
- **Hypotheses**:
  - `Ω : Type u_1`
  - `α β : Type u`
  - `inst✝⁵ : MeasurableSpace Ω`
  - `inst✝⁴ : MeasurableSpace α`
  - `inst✝³ : MeasurableSpace β`
  - `inst✝² : MeasurableSingletonClass β`
  - … (+20 more)
- **Prior tactics**:
  - `rw [← sum_meas_smul_cond_fiber' hY μ]`
  - `apply identDistrib_of_sum _ ((measurable_snd.comp measurable_fst).prodMk measurable_snd) (hX.prodMk hY)`
  - `intro y hy`
  - `have h1 : IdentDistrib (fun ω ↦ (ω.1.2, ω.2)) (fun ω ↦ (ω.1.2, y)) (m y) (m y) := by
  apply IdentDistrib.of_ae_eq ((measurable_snd.comp measurable_fst).prodMk measurable_snd).aemeasurable
  apply Fil …`
  - `have h2 : IdentDistrib (fun ω ↦ (ω.1.2, y)) (fun ω ↦ (X ω, y)) (m y) (μ[|Y ← y]) := by
  apply IdentDistrib.comp _ measurable_prodMk_right
  apply (identDistrib_comp_fst measurable_snd _ _).trans
  ha …`
- **Redacted line**: `exact (h1.trans h2).trans (h3 y)`
- **Query**: identical distribution relation is transitive
- ⚠ **Leakage**: cited-name leakage

### 7. `pfr_step_v2_00267.q1` — scenario: `mathlib_only`

- **Ground truth**: `Measurable.aemeasurable`
- **Tactic kind**: `exact`
- **Source**: `PFR/ForMathlib/Entropy/RuzsaDist.lean:206`
- **Enclosing**: `rdist_of_inj`
- **Goal**: `⊢ AEMeasurable (fun x => x.1 - x.2) ((Measure.map (⇑φ ∘ X) μ).prod (Measure.map (⇑φ ∘ Y) μ'))`
- **Hypotheses**:
  - `Ω : Type u_1`
  - `Ω' : Type u_2`
  - `G : Type u_5`
  - `mΩ : MeasurableSpace Ω`
  - `μ : Measure Ω`
  - `mΩ' : MeasurableSpace Ω'`
  - … (+18 more)
- **Prior tactics**:
  - `· congr 1
  exact entropy_comp_of_injective _ hX _ hφ`
  - `exact entropy_comp_of_injective _ hY _ hφ`
  - `rw [← entropy_comp_of_injective _ (by fun_prop) _ hφ]`
  - `apply IdentDistrib.entropy_congr`
  - `constructor`
- **Redacted line**: `· exact ??? .of_discrete`
- **Query**: AEMeasurable subtraction map for countable codomain product measure
- ⚠ **Leakage**: cited-name leakage

### 8. `pfr_step_v2_00520.q1` — scenario: `mathlib_only`

- **Ground truth**: `ProbabilityTheory.Kernel.measurable_kernel_prodMk_left'`
- **Tactic kind**: `exact`
- **Source**: `PFR/Mathlib/Probability/Kernel/Disintegration.lean:83`
- **Enclosing**: `ProbabilityTheory.Kernel.disintegration`
- **Goal**: `⊢ Measurable fun b => (κ.condKernel (x, b)) (Prod.mk b ⁻¹' s)`
- **Hypotheses**:
  - `S : Type u_2`
  - `T : Type u_3`
  - `U : Type u_4`
  - `inst✝⁸ : Countable S`
  - `inst✝⁷ : MeasurableSpace S`
  - `inst✝⁶ : DiscreteMeasurableSpace S`
  - … (+10 more)
- **Prior tactics**:
  - `have : ⋃ a, Prod.fst ⁻¹' {a} ∩ {su | (a, su.2) ∈ s} = s := by ext a; simp`
  - `conv_lhs => rw [← this]`
  - `rw [measure_iUnion]`
  - `· intro a a' haa'
  rw [Function.onFun, Set.disjoint_iff]
  intro su
  simp only [Set.mem_inter_iff, Set.mem_preimage, Set.mem_singleton_iff, Set.mem_setOf_eq,
    Set.mem_empty_iff_false, and_imp]
   …`
  - `· refine fun _ ↦ (measurable_fst (.singleton _)).inter ?_
  exact measurable_prodMk_left.comp measurable_snd hs`
- **Redacted line**: `exact ??? hs x`
- **Query**: kernel evaluation: fixed measurable set gives measurable parameter map

### 9. `pfr_step_v2_00499.q1` — scenario: `mathlib_only`

- **Ground truth**: `Set.iInter_congr`
- **Tactic kind**: `apply`
- **Source**: `PFR/Mathlib/Probability/Independence/Kernel.lean:54`
- **Enclosing**: `ProbabilityTheory.Kernel.iIndepFun.finsets`
- **Goal**: `⊢ ⋂ (_ : j ∈ s), E j = ⋂ (hx : j ∈ s), ⋂ i, E' ⟨j, hx⟩ i`
- **Hypotheses**:
  - `ι : Type u_1`
  - `α : Type u_2`
  - `Ω : Type u_7`
  - `_mα : MeasurableSpace α`
  - `_mΩ : MeasurableSpace Ω`
  - `κ : Kernel α Ω`
  - … (+26 more)
- **Prior tactics**:
  - `· apply Finset.prod_congr rfl
  intro j _
  rw [Ej_eq j]`
  - `simp only [implies_true]`
  - `rw [Set.iInter_subtype]`
  - `apply Set.iInter_congr`
  - `intro j`
- **Redacted line**: `apply ???`
- **Query**: hypothesis giving for each subtype index, a set equals an intersection

### 10. `pfr_step_v2_00412.q1` — scenario: `local_only`

- **Ground truth**: `tau_strictly_decreases'`
- **Tactic kind**: `apply`
- **Source**: `PFR/ImprovedPFR.lean:760`
- **Enclosing**: `tau_minimizer_exists_rdist_eq_zero`
- **Goal**: `⊢ d[Prod.fst # Prod.snd] = 0`
- **Hypotheses**:
  - `Ω₀₁ : Type u_1`
  - `Ω₀₂ : Type u_2`
  - `inst✝⁸ : MeasureSpace Ω₀₁`
  - `inst✝⁷ : MeasureSpace Ω₀₂`
  - `inst✝⁶ : IsProbabilityMeasure ℙ`
  - `inst✝⁵ : IsProbabilityMeasure ℙ`
  - … (+23 more)
- **Prior tactics**:
  - `linarith [(u_mem n).2, p.hη']`
  - `let M : MeasureSpace (G × G) := ⟨(μ n).1.prod (μ n).2⟩`
  - `have : IsProbabilityMeasure ((μ n).1.prod (μ n).2) := by infer_instance`
  - `have : d[@Prod.fst G G # @Prod.snd G G] = d[id ; (μ n).1 # id ; (μ n).2] :=
  IdentDistrib.rdist_congr IdentDistrib.fst_id IdentDistrib.snd_id`
  - `rw [← this]`
- **Redacted line**: `apply ??? (q n) measurable_fst measurable_snd ?_
  (by linarith [(u_mem n).2, p.hη'])`
- **Query**: relative entropy of coordinate projections under product probability measure is zero

### 11. `pfr_step_v2_00804.q1` — scenario: `local_only`

- **Ground truth**: `rho_eq_of_identDistrib`
- **Tactic kind**: `apply`
- **Source**: `PFR/RhoFunctional.lean:1112`
- **Enclosing**: `condRho_of_sum_le`
- **Goal**: `⊢ ρ[fun ω => X ω + s ; μ[|(X + Y) ⁻¹' {s}] # A] = ρ[Y ; μ[|(X + Y) ⁻¹' {s}] # A]`
- **Hypotheses**:
  - `G : Type uG`
  - `inst✝⁵ : AddCommGroup G`
  - `inst✝⁴ : Fintype G`
  - `hGm : MeasurableSpace G`
  - `inst✝³ : DiscreteMeasurableSpace G`
  - `Ω : Type u_1`
  - … (+17 more)
- **Prior tactics**:
  - `simp only [condRho]`
  - `congr with s`
  - `congr 1`
  - `have : ρ[X ; μ[|(X + Y) ⁻¹' {s}] # A] = ρ[fun ω ↦ X ω + s ; μ[|(X + Y) ⁻¹' {s}] # A] := by
  rw [rho_of_translate hX hA]`
  - `rw [this]`
- **Redacted line**: `apply ???`
- **Query**: rho values equal when two functions agree on conditioning set

### 12. `pfr_step_v2_00847.q1` — scenario: `local_only`

- **Ground truth**: `tendsto_rdist_probabilityMeasure`
- **Tactic kind**: `apply`
- **Source**: `PFR/RhoFunctional.lean:1913`
- **Enclosing**: `phiMinimizer_exists_rdist_eq_zero`
- **Goal**: `⊢ Tendsto (fun x => d[Prod.fst ; μ (φ x) # Prod.snd ; μ (φ x)]) atTop (𝓝 d[Prod.fst ; ↑ν # Prod.snd ; ↑ν])`
- **Hypotheses**:
  - `G : Type uG`
  - `inst✝³ : AddCommGroup G`
  - `inst✝² : Fintype G`
  - `hGm : MeasurableSpace G`
  - `inst✝¹ : DiscreteMeasurableSpace G`
  - `A : Finset G`
  - … (+25 more)
- **Prior tactics**:
  - `have I n : phi Prod.fst Prod.snd (u n) A (μ n) ≤ phi X' Y' (u n) A ℙ :=
  hμ n _ _ _ _ hP hX' hY'`
  - `have L1 : Tendsto (fun n ↦ phi Prod.fst Prod.snd (u (φ n)) A (μ (φ n))) atTop
    (𝓝 (phi Prod.fst Prod.snd (1/8) A ν)) := by
  apply Tendsto.add
  · apply tendsto_rdist_probabilityMeasure continuous_ …`
  - `have L2 : Tendsto (fun n ↦ phi X' Y' (u (φ n)) A ℙ) atTop (𝓝 (phi X' Y' (1/8) A ℙ)) :=
  Tendsto.const_add _ (Tendsto.mul_const _ (u_lim.comp φlim))`
  - `exact le_of_tendsto_of_tendsto' L1 L2 (fun n ↦ I _)`
  - `apply Tendsto.add`
- **Redacted line**: `· apply ??? continuous_fst continuous_snd hν`
- **Query**: tendsto of distance of two pushforwards for continuous maps

### 13. `pfr_step_v2_00309.q1` — scenario: `mathlib_only`

- **Ground truth**: `Measurable.aemeasurable`
- **Tactic kind**: `exact`
- **Source**: `PFR/ForMathlib/Entropy/RuzsaDist.lean:1092`
- **Enclosing**: `condRuzsaDist'_of_inj_map'`
- **Goal**: `⊢ AEMeasurable (⟨C, B + C⟩) μ`
- **Hypotheses**:
  - `Ω : Type u_1`
  - `Ω'' : Type u_3`
  - `G : Type u_5`
  - `mΩ : MeasurableSpace Ω`
  - `μ : Measure Ω`
  - `mΩ'' : MeasurableSpace Ω''`
  - … (+27 more)
- **Prior tactics**:
  - `simp [μ']`
  - `constructor`
  - `· exact (hC.prodMk (hB.add hC)).aemeasurable`
  - `· exact (hC'.prodMk (hB'.add hC')).aemeasurable`
  - `· have : ⟨C', B' + C'⟩ = (⟨C, B + C⟩) ∘ Prod.snd := by ext1 _; simp [B', C']
  rw [this, ← Measure.map_map _ measurable_snd]
  · simp only [Measure.map_snd_prod, measure_univ, one_smul, μ']
  · exact  …`
- **Redacted line**: `exact (hC.prodMk (hB.add hC)).aemeasurable`
- **Query**: measurability of pair of measurable functions

### 14. `pfr_step_v2_00488.q1` — scenario: `mathlib_only`

- **Ground truth**: `MeasureTheory.measure_congr`
- **Tactic kind**: `apply`
- **Source**: `PFR/Mathlib/Probability/Independence/Basic.lean:317`
- **Enclosing**: `ProbabilityTheory.iIndepFun.ae_eq`
- **Goal**: `⊢ μ (⋂ i ∈ s, E i) = μ (⋂ i ∈ s, E' i)`
- **Hypotheses**:
  - `Ω : Type u_13`
  - `mΩ : MeasurableSpace Ω`
  - `μ : Measure Ω`
  - `ι : Type u_14`
  - `β : ι → Type u_15`
  - `m : (i : ι) → MeasurableSpace (β i)`
  - … (+12 more)
- **Prior tactics**:
  - `use F`
  - `rcases Classical.axiomOfChoice this with ⟨E', hE'⟩`
  - `have hE'' : ∀ i ∈ s, MeasurableSet[MeasurableSpace.comap (f i) (m i)] (E' i) := by
  intro i hi; exact (hE' i hi).1`
  - `have hE''' : ∀ i ∈ s, E' i =ᵐ[μ] E i := by
  intro i hi; exact (hE' i hi).2`
  - `convert hf_Indep s hE'' using 1 with i`
- **Redacted line**: `· apply ???
  apply EventuallyEq.finite_iInter
  intro i hi
  exact (hE''' i hi).symm`
- **Query**: measure equal for almost everywhere equal sets

### 15. `pfr_step_v2_00368.q1` — scenario: `mathlib_only`

- **Ground truth**: `Set.mem_of_eq_of_mem`
- **Tactic kind**: `exact`
- **Source**: `PFR/HomPFR.lean:54`
- **Enclosing**: `goursat`
- **Goal**: `⊢ x✝.2 - ↑φ x✝.1 ∈ S₂`
- **Hypotheses**:
  - `G : Type u_1`
  - `G' : Type u_2`
  - `inst✝³ : AddCommGroup G`
  - `inst✝² : AddCommGroup G'`
  - `inst✝¹ : Module (ZMod 2) G`
  - `inst✝ : Module (ZMod 2) G'`
  - … (+10 more)
- **Prior tactics**:
  - `intro hx`
  - `let x : H := { val := x, property := hx }`
  - `· constructor
  · exact Set.mem_of_eq_of_mem (hf x).1.symm (f x).1.property
  · exact Set.mem_of_eq_of_mem (hf x).2.symm (f x).2.property`
  - `constructor`
  - `· exact Set.mem_of_eq_of_mem (hf x).1.symm (f x).1.property`
- **Redacted line**: `· exact ??? (hf x).2.symm (f x).2.property`
- **Query**: if a = b and a in S then b in S

