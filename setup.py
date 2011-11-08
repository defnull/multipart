#!/usr/bin/env python

import sys
import os.path
from distutils.core import setup

if sys.version_info < (2,6):
    raise NotImplementedError("Sorry, you need at least Python 2.6 or Python 3.x to use this module.")

from distutils.command.build_py import build_py

from multipart import __version__, __author__, __license__, __doc__

setup(name='multipart',
      version = __version__,
      description = 'Parser for multipart/form-data.',
      long_description = __doc__,
      author = __author__,
      author_email = 'marc@gsites.de',
      url = 'http://github.com/defnull/multipart',
      py_modules = ['multipart'],
      license = __license__,
      platforms = 'any',
      classifiers = ['Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: CGI Tools/Libraries',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 3'],
      cmdclass = {'build_py': build_py}
     )



