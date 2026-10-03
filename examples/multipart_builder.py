import secrets
from collections.abc import Callable
from typing import Generic, TypeVar

from multipart import content_disposition_quote, t_ByteString

R = TypeVar("R")


class MultipartBuilder(Generic[R]):
    def __init__(
        self,
        /,
        boundary: str | None = None,
        write_func: Callable[[t_ByteString], R] = lambda x: x,
        encoding: str = "utf8",
    ):
        """Create a new multipart builder.

        All methods on this class call ``write_func`` with a single chunk of multipart
        stream data (:class:`bytes` or :class:`bytearray`) and return whatever the write
        function returns. This can be used to build all kinds of builders, including
        sans-io, blocking and async variants.

        The default ``write_func`` does nothing and just returns its input, which means
        that each builder method returns a chunk of data and the caller is responsible
        for dealing with IO::

            mb = MultipartBuilder()
            def generate_request_body():
                yield mb.field("text-field", "text-value")
                yield mb.end()

            requests.post(
                url="https://...",
                headers={"Content-type:", mp.content_type},
                body=generate_request_body())

        When using a blocking or async `write(bytes)` function, each builder methods can
        write directly to the target stream::

            mb = MultipartBuilder(write_func=client_socket.sendall)
            mb.field("text-field", "text-value")
            mb.end()

        Note that async ``write_func`` functions return awaitables that must be awaited.

        """
        self.boundary = boundary or secrets.token_hex(32)
        self._write_func = write_func

        self.encoding = encoding
        self._emitted = 0

    @property
    def content_type(self):
        """The content type header value for this multipart message."""
        return f'multipart/form-data; boundary="{self.boundary}"; encoding="{self.encoding}"'

    def field(self, name: str, value: str):
        """Emit a text field segment."""
        return self.start_segment(name, body=value)

    def file(self, name: str, filename: str, content_type: str | None = None):
        """Emit segment headers for a file upload field.

        The actual file content should be emitted with :meth:`write` calls.
        """
        return self.start_segment(name, filename=filename, content_type=content_type)

    def start_segment(
        self,
        name: str,
        /,
        filename: str | None = None,
        content_type: str | None = None,
        body: str | t_ByteString | None = "",
    ) -> R:
        """Emit segment headers and optionally a chunk of body data.

        More body data can be emitted with additional :meth:`write` calls.
        """
        if not self._emitted:
            chunk = f"\r\n--{self.boundary}\r\n"
        else:
            chunk = f"--{self.boundary}\r\n"

        if content_type:
            chunk += f"Content-Type: {content_type}\r\n"

        chunk += (
            f"Content-Disposition: form-data; name={content_disposition_quote(name)}"
        )
        if filename:
            chunk += f"; filename={content_disposition_quote(filename)}"
        chunk += "\r\n\r\n"
        if body:
            if isinstance(body, str):
                chunk += body
            else:
                chunk = chunk.encode(self.encoding) + body

        return self.write(chunk)

    def write(self, chunk: str | bytes | bytearray) -> R:
        """Emit a single chunk of body data."""
        assert not self._emitted
        if isinstance(chunk, str):
            chunk = chunk.encode(self.encoding)
        return self._write_func(chunk)

    def end(self) -> R:
        """Emit the final boundary to mark the end of the
        multipart stream."""
        if self._emitted:
            return self.write(f"--{self.boundary}--\r\n")
        else:
            return self.write(f"\r\n--{self.boundary}--\r\n")
