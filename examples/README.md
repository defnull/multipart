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

## `form_consumer.py`

This example shows a fundamentally different approach to form handling: The
expected form fields and their handling is defined beforehand, which allows the
parser to process the multipart segments in order of arrival and fail fast on
unexpected user input or exceeded limits. Another benefit is that the developer
can specify the desired location for file uploads and avoid unnecessary copy
or move operations. Cleanup actions can be triggered automatically in case of
errors. The API could also be extended to support a rich set of validators and
stream processors (e.g. compression) as needed.

