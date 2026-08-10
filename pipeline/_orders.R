# =============================================================================
# Canonical orderings — ONE declaration, reused everywhere
# =============================================================================
# Sourced by BOTH `_theme.R` (the figure layer) and `10_canonical_common.R`
# (the estimation layer), so a table and the figure that draws it cannot
# disagree about what order things go in or what a category is called.
#
# Before this file existed the two layers each declared their own: the
# estimation layer had `JURIS_C`, `LANGS_C` and `HOME_REGION_C`, the figure
# layer had `JURIS_LEVELS`, `REGION_LEVELS` and `HOME_REGION`. They happened to
# agree. Nothing made them agree, and a model order was additionally re-derived
# inside three different figure scripts from whatever the data happened to
# contain.
#
# RULE: row order in a figure is fixed by one of these vectors, never by the
# estimates being displayed — an order computed from the data makes the ranking
# a property of the thing being shown, so the strongest cells always drift to
# one end and the layout implies a finding. The two deliberate exceptions are
# stated in the legends (Fig 2c per-model rows, Fig 3b foundations), where the
# ordering IS the point.

# --- jurisdictions -----------------------------------------------------------
# Ordered by the size of the home contrast in the first release and then frozen,
# so it is stable across releases rather than re-sorting when an estimate moves.
ORDER_JURIS <- c("CN", "MENA", "India", "US", "EU")

# --- issue regions -----------------------------------------------------------
# The STORED level is "Arab" (the 22 Arab League states, as harvested); every
# figure displays "MENA" so the issue region reads against the MENA jurisdiction
# it is the home region of. Keeping the data value and the display label apart
# avoids a rename that would touch HOME_REGION, the palette and every stored
# estimate table.
ORDER_REGION <- c("China", "Arab", "India", "US", "Europe", "General")
HOME_REGION_OF <- c(CN = "China", MENA = "Arab", India = "India",
                    US = "US", EU = "Europe")

# --- models ------------------------------------------------------------------
# Grouped by developer jurisdiction, alphabetical within group. NOT ordered by
# any estimate. This is the row order for every per-model display.
ORDER_MODEL <- c(
  "deepseek-chat-v3.1", "qwen3-max",                                  # CN
  "allam-7b", "falcon3-10b", "jais-8b",                               # MENA
  "sarvam-30b",                                                       # India
  "claude-opus-4.5", "gpt-4o", "gpt-5.1", "grok-4.3",                 # US
  "mistral-large-2512")                                               # EU
MODEL_JURIS <- c(
  "deepseek-chat-v3.1" = "CN",   "qwen3-max"          = "CN",
  "allam-7b"           = "MENA", "falcon3-10b"        = "MENA",
  "jais-8b"            = "MENA",
  "sarvam-30b"         = "India",
  "claude-opus-4.5"    = "US",   "gpt-4o"             = "US",
  "gpt-5.1"            = "US",   "grok-4.3"           = "US",
  "mistral-large-2512" = "EU")

# --- languages ---------------------------------------------------------------
# English first: it is the paired reference for every language contrast, which
# is a property of the estimand and not a ranking.
ORDER_LANG       <- c("en", "zh", "ar", "ru", "hi")
LANG_LABEL       <- c(en = "English", zh = "Chinese", ar = "Arabic",
                      ru = "Russian", hi = "Hindi")
# The four contrast rows, i.e. everything except the reference. The label form
# is what a display shows; the code form is what the tables key on, and the two
# are kept in the same order so a panel's heading can never drift off its data.
ORDER_LANG_CONTRAST      <- c("Chinese", "Arabic", "Russian", "Hindi")
ORDER_LANG_CONTRAST_CODE <- setdiff(ORDER_LANG, "en")
stopifnot(identical(unname(LANG_LABEL[ORDER_LANG_CONTRAST_CODE]),
                    ORDER_LANG_CONTRAST))

# --- content categories ------------------------------------------------------
ORDER_IDEO_DIM <- c("Economic", "Social", "Authority", "Populism")
ORDER_IDEO_BIN <- c("-2", "-1", "0", "+1", "+2")
# Endpoints are DIMENSION-SPECIFIC: "left/right" is meaningful for the economic
# scale and misleading on the other three, and the codebook makes no such
# mapping. Acceptance fails on a generic left/right label attached to authority
# or populism.
IDEO_ENDPOINTS <- list(
  Economic  = c("left", "right"),
  Social    = c("progressive", "traditional"),
  Authority = c("authoritarian", "libertarian"),
  Populism  = c("populist", "elitist"))

# Descending prevalence in the first release, then frozen — see the rule above.
ORDER_FOUNDATION <- c("Fairness / cheating", "Care / harm",
                      "Liberty / oppression", "Authority / subversion",
                      "Loyalty / betrayal", "Sanctity / degradation")
FOUNDATION_FIELD <- c("Fairness / cheating"    = "fairness_cheating",
                      "Care / harm"            = "care_harm",
                      "Liberty / oppression"   = "liberty_oppression",
                      "Authority / subversion" = "authority_subversion",
                      "Loyalty / betrayal"     = "loyalty_betrayal",
                      "Sanctity / degradation" = "sanctity_degradation")

# --- prompt tiers ------------------------------------------------------------
ORDER_TIER <- c("regular", "boundary")

# --- helpers -----------------------------------------------------------------
f_juris <- function(x) factor(as.character(x), levels = ORDER_JURIS)
f_model <- function(x) factor(as.character(x), levels = ORDER_MODEL)
f_lang  <- function(x) factor(as.character(x), levels = ORDER_LANG)
f_found <- function(x) factor(as.character(x), levels = ORDER_FOUNDATION)
f_dim   <- function(x) factor(as.character(x), levels = ORDER_IDEO_DIM)

# Assert that a vector contains only known members. Called by the estimation
# scripts on load: a roster change should stop the release here, not surface as
# an NA row halfway through a figure.
assert_known <- function(x, allowed, what) {
  bad <- setdiff(unique(as.character(x)), allowed)
  if (length(bad))
    stop(sprintf("unknown %s not in the canonical ordering: %s",
                 what, paste(bad, collapse = ", ")))
  invisible(TRUE)
}
