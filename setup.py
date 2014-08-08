# -*- coding: utf-8 -*-
from setuptools import setup


setup(
    name = "hgapi",
    version = "1.7.2",
    packages = ['hgapi'],
    test_suite = "hgapi.testhgapi.TestHgAPI",
    author = "Fredrik Håård",
    author_email = "fredrik@haard.se",
    description = "Python API to Mercurial using the command-line interface",
    license = "Do whatever you want, don't blame me",
    keywords = "mercurial api",
    url = "https://bitbucket.org/haard/hgapi",
    classifiers = """Development Status :: 5 - Production/Stable
Intended Audience :: Developers
License :: Freely Distributable
License :: OSI Approved :: BSD License
License :: OSI Approved :: MIT License
Operating System :: OS Independent
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Programming Language :: Python :: 3.2
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Topic :: Software Development :: Libraries
Topic :: Software Development :: Version Control""".split('\n'),
    long_description = """
hgapi is a pure-Python API to Mercurial, that uses the command-line
interface instead of the internal Mercurial API. The rationale for
this is twofold: the internal API is unstable, and it is GPL.

hgapi works for any version of Mercurial, including  < 1.9, and will
instantly reflect any changes to the repository. It also has a really
permissive license (do whatever you want, don't blame me).

For example of code that uses this API, take a look at
https://bitbucket.org/haard/autohook which now uses hgapi
exclusively."""
)
