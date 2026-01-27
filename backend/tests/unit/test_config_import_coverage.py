"""Import config modules for coverage.

Diff-cover counts changes in some config schema modules. These tests ensure
those modules are imported during the unit test run so their class bodies
are covered.
"""

# ruff: noqa: D101, D102


def test_import_platform_config_module():
    """Import module so diff-covered schema lines are executed."""
    import airweave.platform.configs.config  # noqa: F401
