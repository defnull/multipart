Parser for multipart/form-data
==============================

.. image:: https://github.com/defnull/multipart/actions/workflows/test.yaml/badge.svg
    :target: https://github.com/defnull/multipart/actions/workflows/test.yaml
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/multipart.svg
    :target: https://pypi.python.org/pypi/multipart/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/l/multipart.svg
    :target: https://pypi.python.org/pypi/multipart/
    :alt: License

This module provides multiple parsers for RFC-7578 ``multipart/form-data``, both
low-level for framework authors and high-level for WSGI application developers:

* ``PushMultipartParser``: A low-level incremental `SansIO <https://sans-io.readthedocs.io/>`_
  (non-blocking) parser suitable for asyncio and other time or memory constrained
  environments.
* ``MultipartParser``: A streaming parser emitting memory- and disk-buffered
  ``MultipartPart`` instances.
* ``parse_form_data``: A helper function to parse both ``multipart/form-data``
  and ``application/x-www-form-urlencoded`` form submissions from a
  `WSGI <https://peps.python.org/pep-3333/>`_ environment.

Installation
------------

``pip install multipart``

Features
--------

* Pure python single file module with no dependencies.
* 100% test coverage. Tested with inputs as seen from actual browsers and HTTP clients.
* Parses multiple GB/s on modern hardware (quick tests, no proper benchmark).
* Quickly rejects malicious or broken inputs and emits useful error messages.
* Enforces configurable memory and disk resource limits to prevent DoS attacks.

**Limitations:** This parser implements ``multipart/form-data`` as it is used by
actual modern browsers and HTTP clients, which means:

* Just ``multipart/form-data``, not suitable for email parsing
* No ``multipart/mixed`` support (RFC 2388, deprecated in RFC 7578)
* No ``encoded-word`` encoding (RFC 2047, no one uses that)
* No ``base64`` or ``quoted-printable`` transfer encoding (not used)
* No ``name=_charset_`` support (discouraged in RFC 7578)

Usage and examples
------------------

For WSGI application developers we strongly suggest using the ``parse_form_data``
helper function. It accepts a WSGI ``environ`` dictionary and parses both types
of form submission (``multipart/form-data`` and ``application/x-www-form-urlencoded``)
based on the actual content type of the request. You'll get two ``MultiDict``
instances in return, one for text fields and the other for file uploads:

.. code-block:: python

    from multipart import parse_form_data

    def wsgi(environ, start_response):
      if environ["REQUEST_METHOD"] == "POST":
        forms, files = parse_form_data(environ)
        
        title = forms["title"]    # string
        upload = files["upload"]  # MultipartPart
        upload.save_as(...)

The ``parse_form_data`` helper function internally uses ``MultipartParser``, a
streaming parser that reads from a ``multipart/form-data`` encoded binary data
stream and emits ``MultipartPart`` instances as soon as a part is fully parsed.
This is most useful if you want to consume the individual parts as soon as they
arrive, instead of waiting for the entire request to be parsed:

.. code-block:: python

    from multipart import parse_options_header, MultipartParser

    def wsgi(environ, start_response):
      assert environ["REQUEST_METHOD"] == "POST"
      ctype, copts = mp.parse_options_header(environ.get("CONTENT_TYPE", ""))
      boundary = copts.get("boundary")
      charset = copts.get("charset", "utf8")
      assert ctype == "multipart/form-data"
    
      parser = mp.MultipartParser(environ["wsgi.input"], boundary, charset)
      for part in parser:
        if part.filename:
          print(f"{part.name}: File upload ({part.size} bytes)")
          part.save_as(...)
        elif part.size < 1024:
          print(f"{part.name}: Text field ({part.value!r})")
        else:
          print(f"{part.name}: Test field, but too big to print :/")

The ``MultipartParser`` handles IO and file buffering for you, but does so using
blocking APIs. If you need absolute control over the parsing process and want to
avoid blocking IO at all cost, then have a look at ``PushMultipartParser``, the
low-level non-blocking incremental ``multipart/form-data`` parser that powers all
the other parsers in this library:

.. code-block:: python

    from multipart import PushMultipartParser

    async def process_multipart(reader: asyncio.StreamReader, boundary: str):
      with PushMultipartParser(boundary) as parser:
        while not parser.closed:
          chunk = await reader.read(1024*46)
          for event in parser.parse(chunk):
            if isinstance(event, list):
              print("== Start of segment")
              for header, value in event:
                print(f"{header}: {value}")
            elif isinstance(event, bytearray):
              print(f"[{len(event)} bytes of data]")
            elif event is None:
              print("== End of segment")


Changelog
---------

* **1.0**

  * A completely new, fast, non-blocking ``PushMultipartParser`` parser, which
    now serves as the basis for all other parsers.
  * Default charset for ``MultipartParser`` headers and text fields changed to
    ``utf8``.
  * Default disk and memory limits for ``MultipartParser`` increased, and
    multiple other limits added for finer control.
  * Undocumented APIs deprecated or removed, some of which were not strictly
    private. This includes parameters for ``MultipartParser`` and some
    ``MultipartPart`` methods, but those should not be used by anyone but the
    parser itself.

* **0.2.5**

  * Don't test semicolon separators in urlencoded data (#33)
  * Add python-requires directive, indicating Python 3.5 or later is required and preventing older Pythons from attempting to download this version (#32)
  * Add official support for Python 3.10-3.12 (#38, #48)
  * Default value of ``copy_file`` should be ``2 ** 16``, not ``2 * 16`` (#41)
  * Update URL for Bottle (#42)

* **0.2.4**

  * Consistently decode non-utf8 URL-encoded form-data

* **0.2.3**

  * Import MutableMapping from collections.abc (#23)
  * Fix a few more ResourceWarnings in the test suite (#24)
  * Allow stream to contain data before first boundary (#25)

* **0.2.2**

  * Fix #21 ResourceWarnings on Python 3

* **0.2.1**

  * Fix #20 empty payload

* **0.2**

  * Dropped support for Python versions below 3.6. Stay on 0.1 if you need Python 2.5+ support.

* **0.1**

  * First release
