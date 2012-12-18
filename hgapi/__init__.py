"""Python API to Mercurial, without using the internal Mercurial API
"""
from . import hgapi as _hgapi
Repo = _hgapi.Repo
