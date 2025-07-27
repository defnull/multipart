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
parameters and features available than shown here, so check out the :doc:`api` to get a full picture.

.. _push-example:

SansIO Parser
=============

All parsers in this library are based on :class:`PushMultipartParser`, a fast,
secure, non-blocking and incremental parser targeted at framework or
application developers that need a high level of control. SansIO_ means that
the parser itself does not make any assumptions about the IO or concurrency model
and can be used in any environment, including coroutines, greenlets or callback-based
protocol handlers. But it also means that you have to deal with IO yourself.

Here is a low-level example how the parser loop may look like in an `asyncio`
based environment:

.. code-block:: python

  import asyncio
  import multipart

  async def process_multipart(reader: asyncio.StreamReader, boundary: str):

    with multipart.PushMultipartParser(boundary) as parser:

      while not parser.closed:

        # Wait for data
        chunk = await reader.read(1024*64)

        # Process a single chunk of incoming data
        for event in parser.parse(chunk):

          if isinstance(event, multipart.MultipartSegment):
            print(f"Start of part with name: {event.name}")
            print(f"Headers: {event.headerlist}")

            if current.filename:
              print(f"Form file upload with filename: {current.filename}")
            else:
              print("Form text field without a filename")

          elif event:  # Non-empty batearray
            print(f"Received {len(event)} bytes of data")

          else:  # None
            print("End of part")

Here is how it works: Once the parser is set up, you wait for a chunk of data
from your client and call :meth:`PushMultipartParser.parse`. The returned
iterator yields zero or more *parser events* and stops as soon as the parser
needs more data or detects the end of the multipart stream. You must fully
consume this event iterator before parsing the next chunk of data.

**Parser Events:** For each multipart segment the parser will emit a single
instance of :class:`MultipartSegment` with header and meta information, followed
by zero or more non-empty :class:`bytearray` instances with chunks from the
segment body, followed by a single :data:`None` event to signal the end of
the current segment.

Once the end of the multipart stream is reached and the last event was emitted,
:attr:`closed` will be true. Any errors or exceeded limits during parsing will
raise :exc:`MultipartError` from the iterator.

Note that the parser is used a context manager here. Closing the parser is
important to detect missing or incomplete parts caused by a premature end
of input. You can also close the parser by passing in an empty chunk of data or
calling :meth:`PushMultipartParser.close` explicitly.

Dealing with IO
---------------

The :meth:`parse() <PushMultipartParser.parse>` method does not know how to
fetch more data. It just stops yielding events and waits for you to call it
again with the next chunk. This low-level mode of operation is very flexible,
but sometimes more complicated than it needs to be.

If you can provide some blocking or async function that returns the next chunk
when called, then you can skip some of the complexity of
:meth:`parse() <PushMultipartParser.parse>` and use
:meth:`parse_blocking() <PushMultipartParser.parse_blocking>` or
:meth:`parse_async() <PushMultipartParser.parse_async>` instead.

Here is what the parser loop may look like in a *blocking* environment. Instead
of an abstract blocking stream you could also read from a socket or ``environ[wsgi.input]``:

.. code-block:: python

    import multipart, io

    def blocking_example(stream: io.BufferedIOBase, boundary: str):
      with multipart.PushMultipartParser(boundary) as parser:
        for event in parser.parse_blocking(stream.read):
          pass  # Handle parser events

And here is the same loop with an *awaitable* stream:

.. code-block:: python

    import multipart, asyncio

    async def async_example(stream: asyncio.StreamReader, boundary: str):
      with multipart.PushMultipartParser(boundary) as parser:
        async for event in parser.parse_async(stream.read):
          pass  # Handle parser events


.. _stream-example:

Buffered Parser
===============

The :class:`MultipartParser` parser is the lazy blocking cousin of
:class:`PushMultipartParser`. It can read from a blocking byte stream (e.g.
``environ["wsgi.input"]``) and emits :class:`MultipartPart` instances that are
either memory- or disk-buffered debending on size.

The main benefit is that you no longer have to assemble the payload chunks of
each segment yourself. It is still a streaming parser, which means you can start
processing the first completed :class:`MultipartPart` instances while the client
still sends more data.

Here is a basic example for a typical WSGI_ application:

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

Results are cached, so you can iterate or call :meth:`MultipartParser.get` or
:meth:`MultipartParser.parts` multiple times without triggering any extra work.

Do not forget to :meth:`close() <MultipartPart.close>` all parts after use to
remove unused temporary files quicker and avoid :exc:`ResourceWarning`.
Framework developers may want to add hooks to automatically frees up resources
after the request ended.


.. _wsgi-example:

WSGI Helper
===========

The WSGI helper functions :func:`is_form_request` and :func:`parse_form_data`
accept a `WSGI environ` dictionary and support both types of form submission 
(``multipart/form-data`` and ``application/x-www-form-urlencoded``) at the same
time and with the same API. You'll get two fully populated :class:`MultiDict`
instances in return, one for text fields and the other for file uploads. All
from a single parser function.

.. code-block:: python

    from multipart import parse_form_data, is_form_request

    def wsgi(environ, start_response):
      if is_form_request(environ):
        forms, files = parse_form_data(environ)

        title  = forms["title"]   # type: string
        upload = files["upload"]  # type: MultipartPart
        upload.save_as(...)

Note that form fields that are too large to fit into memory count as file uploads.
They will end up as :class:`MultipartPart` instances without a
:attr:`filename <MultipartPart.filename>` in the `files` dict instead of `forms`.
This is to protect your app from running out of memory or crashing.

:class:`MultipartPart` instances are buffered to temporary files on disk if they
exceed a certain size. The default limits should be fine for most use cases, but
can be configured if you need to. See :class:`MultipartParser` for configurable
limits.


Flask, Bottle & Co
==================

Most WSGI web frameworks already have multipart functionality built in, but
you may still get better throughput for large files (or better limits control
and security) by switching to a more advanced parser library: 

.. code-block:: python

    import flask
    environ = flask.request.environ  # or bottle.request.environ
    forms, files = multipart.parse_form_data(environ)


Legacy CGI
==========

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

