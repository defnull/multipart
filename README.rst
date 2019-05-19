Parser for multipart/form-data
==============================

This module provides a parser for the multipart/form-data format. It can read
from a file, a socket or a WSGI environment. The parser can be used to replace
cgi.FieldStorage (without the bugs) and works with Python 2.5+ and 3.x (2to3).

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

* **0.2 (in development)**
  * Dropped support for Python versions below 3.6. Stay on 0.1 if you need Python 2.5+ support.

* **0.1 (21.06.2010)**
  * First release
