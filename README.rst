Parser for multipart/form-data
==============================

This module provides a parser for the multipart/form-data format. It can read
from a file, a socket or a WSGI environment. The parser can be used to replace
cgi.FieldStorage (without the bugs) and works with Python 2.5+ and 3.x (2to3).

Features
--------

* Python 2.5+ and 3.x (2to3) support. No dependencies.
* Parses multipart/form-data and application/x-url-encoded.
* Produces useful error messages in 'strict'-mode.
* Uploads of unknown size (missing Content-Length header).
* Fast memory mapped files (io.BytesIO) for small uploads.
* Temporary files on disk for big uploads.
* Memory and disk resource limits to prevent DOS attacks.
* 100% test coverage.

Compared to cgi.FieldStorage()
------------------------------

* Reads directly from a socket (no ``.readline(n)``, just ``.read(n)``).
* Consumes bytes regardless of Python version.
* Is desgined for WSGI, not CGI.
* Is not broken.

Limitations
-----------

* Nested "multipart/mixed" parts are not supported; 
  they are mentioned in RFC 2388, section 4.2 and deprecated (for clients) since RFC 7578, section 4.3.

* The "encoded-word" method (described in RFC 2047) is not supported.

* The MIME headers are expected to be encoded in the charset given to the ``Multipart``/``MultipartParser`` constructor. [For operability considerations, see RFC 7578, section 5.1.]

* The size of headers are not counted against the in-memory limit.

Todo
----

* Support for base64 and quoted-printable transfer encoding.

Licence (MIT)
-------------

    Copyright (c) 2010, Marcel Hellkamp.
    Inspired by the Werkzeug library: http://werkzeug.pocoo.org/

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

