#!/usr/bin/env Rscript
# =============================================================================
# Script 10: Ideology and Moral Foundations Patterns
# =============================================================================
# Surface notable patterns beyond libertarian shift
# Creates tables 39-40 and figures 20-21

library(tidyverse)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

cat(rep("=", 80), "\n", sep = "")
cat("IDEOLOGY AND MORAL PATTERNS ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# Load data
load("pipeline/data_clean.RData")

# Filter to engaged responses only
engaged_data <- data_clean %>% filter(engaged)

cat("\nTotal engaged responses:", nrow(engaged_data), "\n")

# =============================================================================
# Table 39: Ideology Variance by Dimension
# =============================================================================

cat("\nGenerating Table 39: Ideology Variance by Dimension...\n")

t39 <- engaged_data %>%
  summarise(
    econ_mean = mean(economic_left_right, na.rm = TRUE),
    econ_sd = sd(economic_left_right, na.rm = TRUE),
    social_mean = mean(social_left_right, na.rm = TRUE),
    social_sd = sd(social_left_right, na.rm = TRUE),
    auth_lib_mean = mean(authoritarian_libertarian, na.rm = TRUE),
    auth_lib_sd = sd(authoritarian_libertarian, na.rm = TRUE),
    pop_elite_mean = mean(populist_elitist, na.rm = TRUE),
    pop_elite_sd = sd(populist_elitist, na.rm = TRUE)
  ) %>%
  pivot_longer(everything(), names_to = c("dimension", "stat"), names_sep = "_(?=mean|sd)") %>%
  pivot_wider(names_from = stat, values_from = value) %>%
  mutate(
    dimension = case_when(
      dimension == "econ" ~ "Economic L-R",
      dimension == "social" ~ "Social L-R",
      dimension == "auth_lib" ~ "Auth-Lib",
      dimension == "pop_elite" ~ "Pop-Elite"
    )
  )

write_csv(t39, "pipeline/tables/39_ideology_variance_by_dimension.csv")
cat("Saved: pipeline/tables/39_ideology_variance_by_dimension.csv\n")

# Print summary
cat("\nIdeology Variance Summary:\n")
print(t39)

# =============================================================================
# Table 40: Moral Foundation Co-occurrence
# =============================================================================

cat("\nGenerating Table 40: Moral Foundation Co-occurrence...\n")

moral_cols <- c("care_harm", "fairness_cheating", "loyalty_betrayal",
                "authority_subversion", "sanctity_degradation", "liberty_oppression")

# Create co-occurrence matrix
cooccur <- matrix(0, nrow = 6, ncol = 6)
rownames(cooccur) <- colnames(cooccur) <- moral_cols

for (i in 1:6) {
  for (j in 1:6) {
    cooccur[i, j] <- sum(engaged_data[[moral_cols[i]]] & engaged_data[[moral_cols[j]]], na.rm = TRUE)
  }
}

# Convert to long format
t40 <- as.data.frame(cooccur) %>%
  rownames_to_column("foundation1") %>%
  pivot_longer(-foundation1, names_to = "foundation2", values_to = "count") %>%
  mutate(
    foundation1_label = case_when(
      foundation1 == "care_harm" ~ "Care/Harm",
      foundation1 == "fairness_cheating" ~ "Fairness/Cheating",
      foundation1 == "loyalty_betrayal" ~ "Loyalty/Betrayal",
      foundation1 == "authority_subversion" ~ "Authority/Subversion",
      foundation1 == "sanctity_degradation" ~ "Sanctity/Degradation",
      foundation1 == "liberty_oppression" ~ "Liberty/Oppression"
    ),
    foundation2_label = case_when(
      foundation2 == "care_harm" ~ "Care/Harm",
      foundation2 == "fairness_cheating" ~ "Fairness/Cheating",
      foundation2 == "loyalty_betrayal" ~ "Loyalty/Betrayal",
      foundation2 == "authority_subversion" ~ "Authority/Subversion",
      foundation2 == "sanctity_degradation" ~ "Sanctity/Degradation",
      foundation2 == "liberty_oppression" ~ "Liberty/Oppression"
    )
  )

write_csv(t40, "pipeline/tables/40_moral_cooccurrence.csv")
cat("Saved: pipeline/tables/40_moral_cooccurrence.csv\n")

# =============================================================================
# Figure 20: Ideology Density by Dimension
# =============================================================================

cat("\nGenerating Figure 20: Ideology Density by Dimension...\n")

ideology_long <- engaged_data %>%
  select(economic_left_right, social_left_right, authoritarian_libertarian, populist_elitist) %>%
  pivot_longer(everything(), names_to = "dimension", values_to = "score") %>%
  mutate(
    dimension_label = case_when(
      dimension == "economic_left_right" ~ "Economic L-R",
      dimension == "social_left_right" ~ "Social L-R",
      dimension == "authoritarian_libertarian" ~ "Auth-Lib",
      dimension == "populist_elitist" ~ "Pop-Elite"
    ),
    dimension_label = factor(dimension_label,
                              levels = c("Economic L-R", "Social L-R", "Auth-Lib", "Pop-Elite"))
  )

fig20 <- ggplot(ideology_long, aes(x = score, fill = dimension_label)) +
  geom_density(alpha = 0.6, color = NA) +
  facet_wrap(~dimension_label, ncol = 2, scales = "free_y") +
  scale_fill_brewer(palette = "Set2") +
  scale_x_continuous(breaks = seq(-2, 2, 1), limits = c(-2.5, 2.5)) +
  labs(
    title = "Ideology Score Distributions by Dimension",
    subtitle = "Auth-Lib shows 5-10x more variance than Economic L-R",
    x = "Ideology Score (Left/Libertarian ← 0 → Right/Authoritarian)",
    y = "Density"
  ) +
  theme_refusal() +
  theme(
    legend.position = "none",
    panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    strip.background = element_rect(fill = "gray90")
  )

ggsave("pipeline/figures/fig20_ideology_density_by_dimension.pdf", fig20, width = 10, height = 8)
cat("Saved: pipeline/figures/fig20_ideology_density_by_dimension.pdf\n")

# =============================================================================
# Figure 21: Moral Foundation Co-occurrence Heatmap
# =============================================================================

cat("\nGenerating Figure 21: Moral Foundation Co-occurrence Heatmap...\n")

fig21 <- ggplot(t40, aes(x = foundation1_label, y = foundation2_label, fill = count)) +
  geom_tile(color = "white", size = 1) +
  geom_text(aes(label = count), color = "black", size = 3) +
  scale_fill_gradient(low = "white", high = "#E41A1C") +
  labs(
    title = "Moral Foundation Co-occurrence Patterns",
    subtitle = "Diagonal shows individual foundation frequencies, off-diagonal shows co-activation",
    x = NULL,
    y = NULL,
    fill = "Count"
  ) +
  theme_refusal() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, size = 10),
    axis.text.y = element_text(size = 10),
    plot.title = element_text(face = "bold", size = 14),
    panel.grid = element_blank()
  ) +
  coord_fixed()

ggsave("pipeline/figures/fig21_moral_cooccurrence_heatmap.pdf", fig21, width = 9, height = 8)
cat("Saved: pipeline/figures/fig21_moral_cooccurrence_heatmap.pdf\n")

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n", rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

# Key findings
cat("\nKey Pattern 1: Economic Inertness\n")
cat(sprintf("  Economic L-R Mean: %.3f (near zero)\n", t39$mean[t39$dimension == "Economic L-R"]))
cat(sprintf("  Economic L-R SD: %.3f\n", t39$sd[t39$dimension == "Economic L-R"]))

cat("\nKey Pattern 2: Auth-Lib as Primary Differentiator\n")
cat(sprintf("  Auth-Lib SD: %.3f\n", t39$sd[t39$dimension == "Auth-Lib"]))
cat(sprintf("  Ratio (Auth-Lib / Economic): %.1fx\n",
            t39$sd[t39$dimension == "Auth-Lib"] / t39$sd[t39$dimension == "Economic L-R"]))

# Most co-activated foundations
cat("\nKey Pattern 3: Most Co-activated Foundation Pairs (off-diagonal):\n")
top_pairs <- t40 %>%
  filter(foundation1 != foundation2) %>%
  arrange(desc(count)) %>%
  head(5)
print(top_pairs %>% select(foundation1_label, foundation2_label, count))

cat("\n", rep("=", 80), "\n", sep = "")
cat("IDEOLOGY AND MORAL PATTERNS ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
