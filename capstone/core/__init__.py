"""Package shim: expose inner `core` package modules at `capstone/core`.

The implementation lives under `capstone/core/core/` (an extra nested
directory). To allow imports like `from core.approval_workflow import ...`
when running tests with working-directory set to `capstone`, add the
inner package directory to this package's `__path__` so standard import
mechanics find the real submodules.
"""

import os

# Path to the nested implementation directory (capstone/core/core)
_this_dir = os.path.dirname(__file__)
_inner_dir = os.path.join(_this_dir, 'core')

if os.path.isdir(_inner_dir) and _inner_dir not in __path__:
    # Prepend so these modules take precedence during import resolution
    __path__.insert(0, _inner_dir)

