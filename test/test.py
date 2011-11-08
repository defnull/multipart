#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest
import sys
import os
import glob

os.chdir(os.path.dirname(os.path.abspath(__file__)))

unittests = [name[2:-3] for name in glob.glob('./test_*.py')]
suite = unittest.defaultTestLoader.loadTestsFromNames(unittests)


def run():
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    sys.exit((result.errors or result.failures) and 1 or 0)


if __name__ == '__main__':
    run()
