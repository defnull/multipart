.. py:currentmodule:: multipart

.. _HTML5: https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#multipart-form-data
.. _RFC7578: https://www.rfc-editor.org/rfc/rfc7578
.. _WSGI: https://peps.python.org/pep-3333
.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _SansIO: https://sans-io.readthedocs.io/
.. _asyncio: https://docs.python.org/3/library/asyncio.html

==================
Usage and Examples
==================

Here are some basic examples for the most common use cases. There are more
parameters and features available than shown here, so check out the docstrings
(or your IDEs built-in help) to get a full picture.


.. _wsgi-example:

WSGI helper
===========

The WSGI helper functions :func:`is_form_request` and :func:`parse_form_data`
accept a `WSGI environ` dictionary and support both types of form submission
(``multipart/form-data`` and ``application/x-www-form-urlencoded``) at once.
You'll get two fully populated :class:`MultiDict` instances in return, one for
text fields and the other for file uploads:

.. code-block:: python

    from multipart import parse_form_data, is_form_request

    def wsgi(environ, start_response):
      if is_form_request(environ):
        forms, files = parse_form_data(environ)

        title  = forms["title"]   # type: string
        upload = files["upload"]  # type: MultipartPart
        upload.save_as(...)

Note that form fields that are too large to fit into memory will end up as
:class:`MultipartPart` instances in the :class:`files` dict instead. This is to protect
your app from running out of memory or crashing. :class:`MultipartPart` instances are
buffered to temporary files on disk if they exceed a certain size. The default
limits should be fine for most use cases, but can be configured if you need to.
See :class:`MultipartParser` for configurable limits.

Flask, Bottle & Co
------------------

Most WSGI web frameworks already have multipart functionality built in, but
you may still get better throughput for large files (or better limits control)
by switching parsers: 

.. code-block:: python

    forms, files = multipart.parse_form_data(flask.request.environ)

Legacy CGI
----------

If you are in the unfortunate position to have to rely on CGI, but can't use
:class:`cgi.FieldStorage` anymore, it's possible to build a minimal WSGI environment
from a CGI environment and use that with :func:`parse_form_data`. This is not a real
WSGI environment, but it contains enough information for :func:`parse_form_data`
to do its job. Do not forget to add proper error handling. 

.. code-block:: python

    import sys, os, multipart

    environ = dict(os.environ.items())
    environ['wsgi.input'] = sys.stdin.buffer
    forms, files = multipart.parse_form_data(environ)


.. _stream-example:

Streaming parser
==================================

The WSGI helper functions may be convenient, but they expect a WSGI environment
and parse the entire request in one go. If you need more control, you can use
:class:`MultipartParser` directly. This streaming parser reads from any blocking
byte stream (e.g. ``environ["wsgi.input"]``) and emits :class:`MultipartPart`
instances that are either memory- or disk-buffered debending on size. If used as
an iterator, the parser will yield parts as soon as they are complete and not
wait for the entire request to be parsed. This allows applications to process
parts (or abort the request) before the request is fully transmitted.

.. code-block:: python

    from multipart import parse_options_header, MultipartParser

    def wsgi(environ, start_response):
      content_type, options = parse_options_header(environ["CONTENT_TYPE"])

      if content_type == "multipart/form-data" and 'boundary' in options:
        stream = environ["wsgi.input"]
        boundary = options["boundary"]
        parser = MultipartParser(stream, boundary)

        for part in parser:
          if part.filename:
            print(f"{part.name}: File upload ({part.size} bytes)")
            part.save_as(...)
          elif part.size < 1024:
            print(f"{part.name}: Text field ({part.value!r})")
          else:
            print(f"{part.name}: Test field, but too big to print :/")

        # Free up resources after use
        for part in parser.parts():
          part.close()

Results are cached, so you can iterate or call
:meth:`MultipartParser.get` or :meth:`MultipartParser.parts` multiple times
without triggering any extra work. Do not forget to :meth:`close <MultipartPart.close>`
all parts after use to free up resources and avoid :exc:`ResourceWarnings<ResourceWarning>`.
Framework developers may want to add logic that automatically frees up resources
after the request ended.

.. _push-example:

SansIO parser
=========================================

All parsers in this library are based on :class:`PushMultipartParser`, a fast
and secure SansIO_ (non-blocking, incremental) parser targeted at framework or
application developers that need a high level of control. `SansIO` means that
the parser itself does not make any assumptions about the IO or concurrency model
and can be used in any environment, including coroutines, greenlets, callbacks
or threads. But it also means that you have to deal with IO yourself. Here is
an example that shows how it can be used in an asyncio_ based application:

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
            elif result:  # Non-empty bytearray
              print(f"[received {len(result)} bytes of data]")
            else:         # None
              print(f"== End of segment")

Once the parser is set up, you feed it bits of data and receive zero or more
result events in return. For each part in a valid multipart stream, the parser
will emit a single :class:`MultipartSegment` instance, followed by zero or more
non-empty content chunks (:class:`bytearray`), followed by a single :data:`None`
to signal the end of the current part. The generator returned by
:meth:`PushMultipartParser.parse` will stop if more data is needed, or raise
:exc:`MultipartError` if it encounters invalid data. Once the parser detects the
end of the multipart stream, :attr:`PushMultipartParser.closed` will be true and
you can stop parsing.

Note that the parser is a context manager. This ensures that the parser actually
reached the end of input and found the final multipart delimiter. Calling
:meth:`PushMultipartParser.close` or exiting the context manager will raise
:exc:`MultipartError` if the parser is still expecting more data.
