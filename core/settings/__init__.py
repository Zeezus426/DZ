"""Settings module for DZ Commodities project."""

import os

# Determine which settings to use based on environment variable
# Default to 'local' for development, use 'prod' for production
settings_module = os.environ.get('DJANGO_SETTINGS_ENV', 'local')

if settings_module == 'prod':
    from .prod import *
elif settings_module == 'local':
    from .local import *
else:
    raise ValueError(f"Invalid DJANGO_SETTINGS_ENV: {settings_module}. Must be 'local' or 'prod'.")
