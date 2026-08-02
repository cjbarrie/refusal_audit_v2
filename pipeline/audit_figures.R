source("pipeline/_theme.R")
figs <- list.files("pipeline/figures", pattern = "[.]png$")
other <- setdiff(list.files("pipeline/figures"), figs)
cat(sprintf("1. exports         : %d png   %s\n", length(figs),
    ifelse(length(other) == 0, "OK - png only",
           paste("*** STRAY:", paste(other, collapse = ", "), "***"))))
src <- readLines("pipeline/11_figures.R", warn = FALSE)
hex <- grep("#[0-9A-Fa-f]{6}", src, value = TRUE)
cat(sprintf("2. hardcoded hex   : %d  %s\n", length(hex),
    ifelse(length(hex) <= 4, "OK (F5 four-step ramp only)", "*** PALETTE LEAK ***")))
ng <- length(grep("ggsave[(]", grep("^\\s*#", src, value=TRUE, invert=TRUE)))
cat(sprintf("3. ggsave calls    : %d  %s\n", ng, ifelse(ng == 0, "OK (save_fig is sole writer)", "*** LEAK ***")))
nt <- length(grep("title *=|subtitle *=", src))
cat(sprintf("4. in-panel titles : %d  %s\n", nt, ifelse(nt == 0, "OK - none", "*** PRESENT ***")))
cat(sprintf("5. jurisdiction    : %s\n", paste(JURIS_LEVELS, collapse = " > ")))
cat(sprintf("   region order    : %s\n", paste(REGION_LEVELS, collapse = " > ")))
cat(sprintf("   home mapping    : %s\n", paste(names(HOME_REGION), HOME_REGION, sep = "->", collapse = "  ")))
if (requireNamespace("farver", quietly = TRUE)) {
  l <- round(farver::decode_colour(unname(PAL_JURIS), to = "lab")[, 1], 0)
  cat(sprintf("6. palette L*      : %s\n", paste(names(PAL_JURIS), l, sep = "=", collapse = "  ")))
  cat(sprintf("   min L* gap      : %d  %s\n", min(diff(sort(l))),
      ifelse(min(diff(sort(l))) >= 8, "OK for grayscale", "*** TOO CLOSE - relies on the size channel ***")))
}
cat("7. uncertainty     : F1 issue-clustered bootstrap percentile; F2/F3/F6 Wilson;\n")
cat("                     F4 none (shows a within-model shift); F5 none (composition)\n")
cat("8. sample          : English-only in F1/F2/F4/F5/F6; F3 adds Chinese for CN models\n")
