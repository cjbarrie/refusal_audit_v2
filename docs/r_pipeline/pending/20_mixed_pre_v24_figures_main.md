# Pending `20_mixed_pre_v24_figures_main.R`

Status: retained pre-v2.4 artwork code; not run by `make_release.R`.

The script read a mixed estimate surface and drew three main figures: home
associations under several old outcome definitions, paired language contrasts,
and a content figure combining ideological slant, moral foundations and
agreement. It fit no statistical models, but its row-selection contract depended
on tables that are no longer current and on content outcomes without an adopted
measurement.

Its historical outputs were Fig1--Fig3 plus a layout RDS. They are not permitted
in the current main-figure directory. The live `pipeline/20_figures_main.R`
reads only final v2.4 `c04` and `c08` rows and writes two PNGs. Do not revive one
panel from this pending script without first promoting its source estimand and
adding it to the exact acceptance inventory.
