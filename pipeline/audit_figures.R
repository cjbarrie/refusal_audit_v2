# Consistency audit for the figure system. Run after 11_figures.R.
source("pipeline/_theme.R")
src <- readLines("pipeline/11_figures.R", warn = FALSE)
code <- grep("^\\s*#", src, value = TRUE, invert = TRUE)
png <- list.files("pipeline/figures", pattern = "[.]png$")
oth <- setdiff(list.files("pipeline/figures"), png)
chk <- function(lab, ok, detail) cat(sprintf("  %-34s %-4s %s\n", lab, ifelse(ok,"OK","FAIL"), detail))

cat("FIGURE SYSTEM AUDIT\n", strrep("-", 72), "\n", sep = "")
# PROJECT RULE: PNG only. Anything else in pipeline/figures/ is a failure.
chk("PNG-only output", length(oth) == 0,
    sprintf("%d png, %d non-png%s", length(png), length(oth),
            if (length(oth)) paste0(" [", paste(oth, collapse = ", "), "]") else ""))
chk("no in-panel titles", length(grep("title *=|subtitle *=", code)) == 0,
    sprintf("%d matches", length(grep("title *=|subtitle *=", code))))
chk("save_fig is sole writer", length(grep("ggsave[(]", code)) == 0,
    sprintf("%d direct ggsave", length(grep("ggsave[(]", code))))
hex <- grep("#[0-9A-Fa-f]{6}", code, value = TRUE)
chk("palette not leaked into script", length(hex) <= 2,
    sprintf("%d literal hex (neutral cell ramp only)", length(hex)))
chk("jurisdiction colours defined once", length(PAL_JURIS) == 5,
    paste(names(PAL_JURIS), collapse = " "))
chk("region colours match jurisdictions",
    all(PAL_REGION[unname(HOME_REGION[JURIS_LEVELS])] == PAL_JURIS[JURIS_LEVELS]),
    "home region inherits its jurisdiction colour")
L <- round(farver::decode_colour(unname(PAL_JURIS), to = "lab")[, 1])
gaps <- c(normal = min(diff(sort(L))))
for (f in c("deutan", "protan", "tritan")) {
  s <- do.call(f, list(unname(PAL_JURIS)), envir = asNamespace("colorspace"))
  gaps[f] <- min(diff(sort(round(farver::decode_colour(s, to = "lab")[, 1]))))
}
chk("grayscale / CVD separation", all(gaps >= 5),
    paste(sprintf("%s %d", names(gaps), gaps), collapse = "  "))
chk("portable fonts", FONT_SANS %in% c("Helvetica","Arial","sans") &&
    FONT_MONO %in% c("Courier","mono"), sprintf("%s / %s", FONT_SANS, FONT_MONO))
cat(strrep("-", 72), "\n")
cat("  ordering   jurisdiction ", paste(JURIS_LEVELS, collapse=" > "), "\n")
cat("             region       ", paste(REGION_LEVELS, collapse=" > "), "\n")
cat("  uncertainty  B issue-clustered bootstrap; C/D Wilson; E/F/G point estimates\n")
cat("  scales       B and E share no axis (different estimands); C/D share refusal-rate %\n")
