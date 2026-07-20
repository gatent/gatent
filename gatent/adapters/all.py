"""Single import that registers every solo_local adapter.

Usage:
    import gatent.adapters.all  # noqa: F401  side-effect: registers all adapters
"""

# State stores
import gatent.adapters.state_stores.sqlite_store  # noqa: F401

# Config stores
import gatent.adapters.config_stores.yaml_files  # noqa: F401

# Vaults
import gatent.adapters.vaults.keychain  # noqa: F401

# Runners
import gatent.adapters.runners.local_python  # noqa: F401

# Extractors
import gatent.adapters.extractors.css  # noqa: F401
import gatent.adapters.extractors.json_path  # noqa: F401

# Transformers
import gatent.adapters.transformers.regex  # noqa: F401
import gatent.adapters.transformers.coalesce  # noqa: F401
import gatent.adapters.transformers.cast  # noqa: F401

# Sinks
import gatent.adapters.sinks.json_lines  # noqa: F401
import gatent.adapters.sinks.webhook  # noqa: F401

# Notifiers
import gatent.adapters.notifiers.stdout  # noqa: F401
import gatent.adapters.notifiers.ntfy  # noqa: F401

# Triggers
import gatent.adapters.triggers.cron  # noqa: F401
import gatent.adapters.triggers.manual  # noqa: F401
