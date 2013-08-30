"""
    Python API to Mercurial, without using the internal Mercurial API.
"""
from . import hgapi as _hgapi
Repo = _hgapi.Repo
HgException = _hgapi.HgException
hg_version = _hgapi.Repo.hg_version
hg_clone = _hgapi.Repo.hg_clone
