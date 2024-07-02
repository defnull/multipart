Parser for multipart/form-data
==============================

This module provides a parser for the multipart/form-data format. It can read
from a file, a socket or a WSGI environment. The parser can be used to replace
cgi.FieldStorage to work around its limitations.

Features
--------

* Parses ``multipart/form-data`` and ``application/x-www-form-urlencoded``.
* Produces useful error messages in 'strict'-mode.
* Gracefully handle uploads of unknown size (missing ``Content-Length`` header).
* Fast memory mapped files (io.BytesIO) for small uploads.
* Temporary files on disk for big uploads.
* Memory and disk resource limits to prevent DOS attacks.
* Fixes many shortcomings and bugs of ``cgi.FieldStorage``.
* 100% test coverage.

Limitations
-----------

* Only parses ``multipart/form-data`` as seen from actual browsers.

  * Not suitable as a general purpose multipart parser (e.g. for multipart emails).
  * No ``multipart/mixed`` support (RFC 2388, deprecated in RFC 7578)
  * No ``encoded-word`` encoding (RFC 2047).
  * No ``base64`` or ``quoted-printable`` transfer encoding.
  
* Part headers are expected to be encoded in the charset given to the ``Multipart``/``MultipartParser`` constructor.
  [For operability considerations, see RFC 7578, section 5.1.]
* The size of headers are not counted against the in-memory limit (todo).

Changelog
---------

* **0.2.5 (18.06.2024)**

  * Don't test semicolon separators in urlencoded data (#33)
  * Add python-requires directive, indicating Python 3.5 or later is required and preventing older Pythons from attempting to download this version (#32)
  * Add official support for Python 3.10-3.12 (#38, #48)
  * Default value of ``copy_file`` should be ``2 ** 16``, not ``2 * 16`` (#41)
  * Update URL for Bottle (#42)

* **0.2.4 (27.01.2021)**

  * Consistently decode non-utf8 URL-encoded form-data

* **0.2.3 (20.11.2020)**

  * Import MutableMapping from collections.abc (#23)
  * Fix a few more ResourceWarnings in the test suite (#24)
  * Allow stream to contain data before first boundary (#25)

* **0.2.2 (04.09.2020)**

  * Fix #21 ResourceWarnings on Python 3

* **0.2.1 (13.06.2020)**

  * Fix #20 empty payload

* **0.2 (19.03.2019)**

  * Dropped support for Python versions below 3.6. Stay on 0.1 if you need Python 2.5+ support.

* **0.1 (21.06.2010)**

  * First release
