"""Phase 3 of repo-market-model: latent reserves and deployable liquidity.

Nothing is estimated yet; see PLAN.md. Every input is read through the parent's
as-of guards (`repo_model.asof`), never re-implemented here.
"""

#: The parent commit this repository is pinned to (pyproject.toml).
PARENT_COMMIT = "71ab387e5557cc9ecefb12d1b2bf21d086571388"

#: The parent's published panel digest at that commit (its metadata/funding_panel_manifest.json).
PANEL_SHA256 = "4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999"
