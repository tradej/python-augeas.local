#!/usr/bin/env python

"""
setup.py file for augeas
"""

import os
prefix = os.environ.get("prefix", "/usr")

from distutils.core import setup

setup (name = 'python-augeas',
       version = '0.4.1',
       author      = "Harald Hoyer",
       author_email = "augeas-devel@redhat.com",
       description = """Python bindings for Augeas""",
       py_modules = [ "augeas" ],
       url = "http://augeas.net/",
       )
