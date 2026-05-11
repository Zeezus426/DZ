"""
Settings module factory.
Dynamically loads settings based on DJANGO_SETTINGS_MODULE or environment.
"""

import os

# Default to local if not specified
environment = os.environ.get('DJANGO_ENV', 'local')

if environment == 'production':
    from .production import *
elif environment == 'local':
    from .local import *
else:
    from .local import *
