# Examples and experimental APIs

This folder contains ideas and examples on how to use `PushMultipartParser` to
build more user friendly parser APIs, or experimental features that are not
ready yet for integration into the core library. The examples are intended for
application or framework developers to ~~steal~~ draw inspiration from.

All files in this folder are dual-licensed as MIT and CC0 so you can use them as
you whish, with or without attribution.


## `async_stream_wrapper.py`

This example shows an `async` aware stream parser that automatically fetches and
parses more data as needed and provides `await`-able methods to read part content.

While this type of API is way easier than using a low-level `PushMultipartParser`,
the *streaming* aspect may still cause issues for application developers. Parts
are not buffered to disk, which means they must be consumed in order of arrival
and can only be consumed once.

Implementing a disk-buffered version that allows repeated or out-of-order reads
is left an an exercise for framework authors for now. Pull requests are welcomed!

Here is how this wrapper would be used:

```python
from multipart import t_AsyncReader, parse_options_header, PushMultipartParser
from async_stream_wrapper import AsyncMultipartStreamWrapper

async def handle_request(headers: dict[str, str], body_reader: t_AsyncReader):
    ctype, options = parse_options_header(headers["content-type"])
    assert ctype == "multipart/form-data"
    parser = AsyncMultipartStreamWrapper(
        PushMultipartParser(boundary=options["boundary"]), body_reader
    )

    async for part in parser:
        print(f"Found: {part.name} ({part.filename or '-'})")
        async for chunk in part.iter_chunks(1024 * 64):
            print(f"[{len(chunk)} bytes]")
        print(f"Total size: {part.size}")
```

## `multipart_builder.py`

This example shows a `MultipartBuilder` class that generates valid `multipart/form-data`,
one chunk at a time. The builder does not perform any I/O itself, but instead passes each
output chunk through a customizable `write_func` and then returns the result of the writer
function. This allows the same builder implementation to be used in any environment:
blocking or async write functions, body generators, or fully Sans-IO patterns are all
supported out of the box.

The default `write_func` does nothing and just returns its input, which means that every
builder method returns a chunk of the multipart message. This can be used to generate
huge multipart request payloads on demand and stream them to a server:

```python
import requests

from multipart_builder import MultipartBuilder

mb = MultipartBuilder()

def body():
    yield mb.field("title", "Large Upload Example")
    yield mb.file("upload", "example.txt", "text/plain")
    with open("example.txt", "rb") as file:
        while chunk := file.read(64 * 1024):
            yield mb.write(chunk)
    yield mb.end()

requests.post(
    "https://...",
    headers={"Content-Type": mb.content_type},
    data=body(),
)
```

This body generator first calls `field(name, value)` to emit the multipart
equivalent of a simple text field. The `file(name, filename, ...)` method
does not take a value. You usually do not want to load entire files into memory,
but stream them chunk by chunk via `write(chunk)` instead. Once all fields
are written, call `end()` to emit the final boundary and properly terminate the
the multipart stream.

We can pass this body iterator to our HTTP client library and use `mb.content_type`
as the `Content-Type` header value. It contains the `mb.boundary` randomly generated
by the builder if none is provided.

The above example shows a *pull* IO model: The HTTP client library asks for more body data
as soon as it's ready to send. Some client frameworks may implement *push* model instead:
They give you a writeable stream, and the write function blocks (or is awaited) until the
write is complete and there is enough room in the output buffer for the next chunk.

Here is an example that writes to an async stream:

```python
import asyncio

from multipart import t_AsyncWriter
from multipart_builder import MultipartBuilder

async def write_request_body(stream: asyncio.StreamWriter):

    async def write(chunk):
        stream.write(chunk)
        await stream.drain()

    mb = MultipartBuilder(write_func=write)

    await mb.field("title", "Large Upload Example")
    await mb.file("upload", "example.txt", "text/plain")
    with await asyncio.to_thread(open, "example.txt", "rb") as file:
        while chunk := await asyncio.to_thread(file.read, 64 * 1024):
            await mb.write(chunk)
    await mb.end()
```

In this version, `stream` is the async request body stream and `write_func` is
set to an async write function. Since `MultipartBuilder` methods return the
result of `write_func`, they will now look like async methods to the caller
and should be awaited, too. We do not care about the actual results, the `write`
function does not return anything useful.
