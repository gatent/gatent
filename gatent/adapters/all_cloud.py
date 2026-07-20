"""Register every cloud-profile adapter via import side-effects.

Imported by engine_factory._build_cloud (and anything running the cloud profile):
    import gatent.adapters.all_cloud
"""
import gatent.adapters.runners.browser_playwright  # noqa: F401  registry.runner("browser_playwright")
import gatent.adapters.state_stores.supabase        # noqa: F401  registry.state_store("supabase")
import gatent.adapters.config_stores.notion         # noqa: F401  registry.config_store("notion")
import gatent.adapters.vaults.cloud_vault           # noqa: F401  registry.vault("cloud_vault")
