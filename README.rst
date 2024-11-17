=================================
Python multipart/form-data parser
=================================

.. image:: https://github.com/defnull/multipart/actions/workflows/test.yaml/badge.svg
    :target: https://github.com/defnull/multipart/actions/workflows/test.yaml
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/multipart.svg
    :target: https://pypi.python.org/pypi/multipart/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/l/multipart.svg
    :target: https://pypi.python.org/pypi/multipart/
    :alt: License

.. _HTML5: https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#multipart-form-data
.. _RFC7578: https://www.rfc-editor.org/rfc/rfc7578
.. _WSGI: https://peps.python.org/pep-3333
.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _SansIO: https://sans-io.readthedocs.io/
.. _asyncio: https://docs.python.org/3/library/asyncio.html

This module provides a fast incremental non-blocking parser for RFC7578_
``multipart/form-data``, as well as blocking alternatives for easier use in
WSGI_ or CGI applications:

* ``PushMultipartParser``: Incremental and non-blocking (SansIO_) parser
  suitable for ASGI_, asyncio_ and other time or memory constrained environments.
* ``MultipartParser``: Streaming parser that yields memory- or disk-buffered
  ``MultipartPart`` instances. 
* ``parse_form_data(environ)`` and ``is_form_request(environ)``: Convenience
  functions for WSGI_ applications with support for both ``multipart/form-data``
  and ``application/x-www-form-urlencoded`` form submissions.


Installation
============

``pip install multipart``


Features
========

* Pure python single file module with no dependencies.
* Well tested with inputs from actual browsers and HTTP clients. 100% test coverage.
* Parses multiple GB/s on modern hardware (see `benchmarks <https://github.com/defnull/multipart_bench>`_).
* Quickly rejects malicious or broken inputs and emits useful error messages.
* Enforces configurable memory and disk resource limits to prevent DoS attacks.

**Scope:** This parser implements ``multipart/form-data`` as defined by HTML5_
and RFC7578_ and aims to support all browsers or HTTP clients in use today.
Legacy browsers are supported to some degree, but only if those workarounds do
not impact performance or security. In detail this means:

* Just ``multipart/form-data``, not suitable for email parsing.
* No ``multipart/mixed`` support (deprecated in RFC7578_).
* No ``base64`` or ``quoted-printable`` transfer encoding (deprecated in RFC7578_).
* No ``encoded-word`` or ``name=_charset_`` encoding markers (deprecated in HTML5_).
* No support for clearly broken clients (e.g. invalid line breaks or headers).

Usage and Examples
==================

Here are some basic examples for the most common use cases. There are more
parameters and features available than shown here, so check out the docstrings
(or your IDEs built-in help) to get a full picture.


Helper function for WSGI or CGI
-------------------------------

For WSGI application developers we strongly suggest using the ``parse_form_data``
helper function. It accepts a WSGI ``environ`` dictionary and parses both types
of form submission (``multipart/form-data`` and ``application/x-www-form-urlencoded``)
based on the actual content type of the request. You'll get two ``MultiDict``
instances in return, one for text fields and the other for file uploads:

.. code-block:: python

    from multipart import parse_form_data, is_form_request

    def wsgi(environ, start_response):
      if is_form_request(environ):
        forms, files = parse_form_data(environ)

        title  = forms["title"]   # type: string
        upload = files["upload"]  # type: MultipartPart
        upload.save_as(...)

Note that form fields that are too large to fit into memory will end up as
``MultipartPart`` instances in the ``files`` dict instead. This is to protect
your app from running out of memory or crashing. ``MultipartPart`` instances are
buffered to temporary files on disk if they exceed a certain size. The default
limits should be fine for most use cases, but can be configured if you need to.
See ``MultipartParser`` for details.

Flask, Bottle & Co
^^^^^^^^^^^^^^^^^^

Most WSGI web frameworks already have multipart functionality built in, but
you may still get better throughput for large files (or better limits control)
by switching parsers: 

.. code-block:: python

    forms, files = multipart.parse_form_data(flask.request.environ)

Legacy CGI
^^^^^^^^^^

If you are in the unfortunate position to have to rely on CGI, but can't use
``cgi.FieldStorage`` anymore, it's possible to build a minimal WSGI environment
from a CGI environment and use that with ``parse_form_data``. This is not a real
WSGI environment, but it contains enough information for ``parse_form_data``
to do its job. Do not forget to add proper error handling. 

.. code-block:: python

    import sys, os, multipart

    environ = dict(os.environ.items())
    environ['wsgi.input'] = sys.stdin.buffer
    forms, files = multipart.parse_form_data(environ)


Stream parser: ``MultipartParser``
----------------------------------

The ``parse_form_data`` helper may be convenient, but it expects a WSGI
environment and parses the entire request in one go before it returns any
results. Using ``MultipartParser`` directly gives you more control and also
allows you to process ``MultipartPart`` instances as soon as they arrive:

.. code-block:: python

    from multipart import parse_options_header, MultipartParser

    def wsgi(environ, start_response):
      content_type, params = parse_options_header(environ["CONTENT_TYPE"])

      if content_type == "multipart/form-data":
        stream = environ["wsgi.input"]
        boundary = params["boundary"]
        charset = params.get("charset", "utf8")

        parser = MultipartParser(stream, boundary, charset)
        for part in parser:
          if part.filename:
            print(f"{part.name}: File upload ({part.size} bytes)")
            part.save_as(...)
          elif part.size < 1024:
            print(f"{part.name}: Text field ({part.value!r})")
          else:
            print(f"{part.name}: Test field, but too big to print :/")


Non-blocking parser: ``PushMultipartParser`` 
--------------------------------------------

The ``MultipartParser`` handles IO and file buffering for you, but relies on
blocking APIs. If you need absolute control over the parsing process and want to
avoid blocking IO at all cost, then have a look at ``PushMultipartParser``, the
low-level non-blocking incremental ``multipart/form-data`` parser that powers
all the other parsers in this library:

.. code-block:: python

    from multipart import PushMultipartParser, MultipartSegment

    async def process_multipart(reader: asyncio.StreamReader, boundary: str):
      with PushMultipartParser(boundary) as parser:
        while not parser.closed:

          chunk = await reader.read(1024*64)
          for result in parser.parse(chunk):

            if isinstance(result, MultipartSegment):
              print(f"== Start of segment: {result.name}")
              if result.filename:
                print(f"== Client-side filename: {result.filename}")
              for header, value in result.headerlist:
                print(f"{header}: {value}")
            elif result:  # Result is a non-empty bytearray
              print(f"[received {len(result)} bytes of data]")
            else:         # Result is None
              print(f"== End of segment")


License
=======

.. __: https://github.com/defnull/multipart/raw/master/LICENSE

Code and documentation are available under MIT License (see LICENSE__).
