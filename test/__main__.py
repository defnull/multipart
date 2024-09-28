import unittest
import pathlib
import sys

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(pathlib.Path(__file__).parent.parent)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    sys.exit((result.errors or result.failures) and 1 or 0)
