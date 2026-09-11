# External legends for the v2.4 figure set

No title, subtitle or caption is embedded in a PNG. These legends define the
measurement, estimand and uncertainty outside the artwork.

## Figure 1 | Genuine refusal by semantic location and developer jurisdiction

Each row describes one developer jurisdiction and combines two views of the
same English prompt population. On the left, all panels reuse one UMAP fitted to
the 2,496 cached English prompt embeddings; outcomes never enter the projection.
Pale grey denotes no genuine refusal by an observed model in that jurisdiction.
A solid coloured point denotes refusal by one model. A segmented point denotes
refusal by several models, with one equal-angle sector in each refusing model's
colour. Hollow grey points identify incomplete prompt-model coverage rather than
engagement. On the right, hollow grey circles give the descriptive English
home-minus-away difference and red diamonds the nested, full-target standardized
contrast. Model rows give model-specific standardized contrasts in the same
colours used in the map. Lines are issue-cluster percentile-bootstrap 95%
intervals. Every forest panel uses the same percentage-point scale. An open
diamond retains the European aggregate point estimate but suppresses its
unreliable interval; grey crosses mark non-estimable model rows and are not zero
estimates. The maps are descriptive semantic locators. Home contrasts adjust
measured prompt composition but are not causal effects of developer jurisdiction.

## Figure 2 | Genuine-refusal geography and delivered-language contrasts

Top, the fixed prompt geometry is repeated for English, Chinese, Arabic, Russian
and Hindi. Pale grey gives the reference geometry and red point size the
equal-jurisdiction/equal-model genuine-refusal propensity in that delivered
language. Bottom left, diamonds and lines give prompt-paired target-language-
minus-English differences with issue-bootstrap 95% intervals. Bottom right,
tiles give the same difference for each model and language; blue is negative,
red positive, and a black centre marks an interval excluding zero. The aggregate
paired estimand is primary. Model rows are exploratory and are not adjusted for
multiplicity. Language contrasts concern delivery of the tested translations,
conditional on translation equivalence and stable delivery; they are not effects
of a speaker's identity or nationality. UMAP neighbourhoods are qualitative
locators, not statistical clusters or causal effects.

## Extended Data

- **ED1--ED2:** standardized away and home predicted risks. Open grey points are
  away; solid coloured points are home.
- **ED3--ED4:** model-specific paired English and target-language outcome
  levels. Open grey points are English and solid coloured points the target
  language.
- **ED5:** four final response states overall and within each original binary
  engagement label. This compares measurement instruments, not annotator
  accuracy.
- **ED6:** marginal distributions of the five final annotation fields.
- **ED7--ED8:** explicitly labelled model-specific home, language and framing
  contrasts with bootstrap intervals. These are exploratory and have no
  multiplicity adjustment.
- **ED9--ED10:** descriptive topic-domain and issue-region outcome rates.
- **ED11--ED12:** ranked prompt concentration and the number of English models
  exhibiting the outcome for each prompt.
- **ED13:** capability-failure semantic atlas by issue region, delivered
  language and model, using the same fixed geometry as Figure 1.
- **ED14:** English genuine-refusal semantic atlas by model, retaining the
  detailed model-level view outside the compact main figure.

Slant and moral-foundation figures remain pending because no adopted final
outcome measure currently supports them.
