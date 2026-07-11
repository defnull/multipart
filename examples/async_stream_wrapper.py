# SPDX-License-Identifier: MIT OR CC0

from typing import AsyncGenerator, List, Optional, Tuple
from multipart import (
    ParserStateError,
    PushMultipartParser,
    t_AsyncReader,
    t_AsyncWriter,
    ParserLimitReached,
    MultipartSegment,
)

##############################################################################
############################ Async Stream Wrapper #############################
##############################################################################


class AsyncMultipartStreamWrapper:
    """An async-aware wrapper for :class:`PushMultipartParser` that reads bytes from an
    awaitable read function on demand and returns :class:`AsyncMultipartPart` instances
    that offer convenient async read methods for their payload.

    This is still a streaming parser, which means that parts are not buffered to disk
    and can only be consumed once, and only in the order they appear in the multipart
    stream.

    .. versionadded:: 2.0
       (experimental, preview)
    """

    def __init__(
        self,
        parser: PushMultipartParser,
        read: t_AsyncReader,
        chunk_size=1024 * 64,
        text_charset="utf8",
    ):
        """Create a new async parser wrapper.

        :param parser: A fresh and configured instance of :cls:`PushMultipartParser`.
        :param read: An awaitable read function returning th next chunk data.
            See :meth:`PushMultipartParser.parse_async`.
        :param chunk_size: A positive integer limiting how many bytes are requested per
          read operation.
        :param text_charset: Default charset for text fields.
        """
        self.read = read
        self.parser = parser
        self.parse_event_stream = None
        self.chunk_size = chunk_size
        self.text_charset = text_charset

        self.complete = False

        self._events = self.parser.parse_async(self.read, self.chunk_size)
        self._current = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.parser.close(check_complete=not exc_type)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)

    async def next(self) -> Optional["AsyncMultipartPart"]:
        """Return the next :cls:`AsyncMultipartPart`, or `None` if the multipart
        stream ended.

        Fetching the next part will close the previous part, which discards any
        remaining data in that part. See :meth:`AsyncMultipartPart.close`.

        This can raise the same exceptions as :meth:`PushMultipartParser.parse_async`.
        """
        if self.complete:
            return

        if self._current and not self._current.closed:
            await self._current.close()
            self._current = None

        try:
            segment = await anext(self._events)
            assert isinstance(segment, MultipartSegment)
            self._current = self._create_part(segment)
            return self._current
        except StopAsyncIteration:
            self.complete = True
            return

    def _create_part(self, segment) -> "AsyncMultipartPart":
        """(overrideable) Create the next :class:`AsyncMultipartPart`."""
        return AsyncMultipartPart(self, segment)

    async def __aiter__(self) -> AsyncGenerator["AsyncMultipartPart", None]:
        """Yield all (remaining) parts by calling :meth:`next` in a loop."""
        while part := await self.next():
            yield part


class AsyncMultipartPart:
    """A wrapper for :class:`MultipartSegment` that represens a single part of a
    multipart stream and also provides async read functions for its body content.

    The body content is not stored or buffered, but streamed directly from the
    backing :cls:`AsyncMultipartStreamParser` instead. It can only be consumed once,
    and is no longer available once the part is closed or the next part has been
    requested.

    All read operations may raise the same exceptions as :meth:`PushMultipartParser.parse_async`.
    """

    #: The underlying :cls:`MultipartSegment`.
    segment: MultipartSegment

    #: True if the parser found the end of the segment and its final :attr:`size` is known.
    complete: bool
    #: True if there is no more data left to be read.
    consumed: bool
    #: True if the part was closed. Reading is no longer allowed.
    closed: bool

    #: Ordered list of headers as (name, value) pairs. Header names are
    #: normalized (Title-Case) and values are stripped of leading or tailing
    #: whitespace.
    headerlist: List[Tuple[str, str]]

    #: The cleaned up `Content-Disposition` header value without any header
    #: options. This will always be 'form-data' for HTTP form submissions.
    disposition: Optional[str]
    #: The 'name' option of the `Content-Disposition` header. For `form-data`
    #: this will always be a string, but the string may be empty.
    name: Optional[str]
    #: The optional 'filename' option of the `Content-Disposition` header.
    filename: Optional[str]

    #: The cleaned up `Content-Type` segment header without any header options.
    content_type: Optional[str]
    #: The optional 'charset' option of the `Content-Type` header.
    charset: Optional[str]

    def __init__(self, parser: AsyncMultipartStreamWrapper, segment: MultipartSegment):
        self.segment = segment

        self.consumed = False
        self.closed = False

        self._parser = parser
        self._buffer = b""

        # Cache these for performance, as they are very likely used
        self.name = segment.name
        self.filename = segment.filename

    def header(self, name: str, default=None):
        """Return the value of a header if present, or a default value."""
        return self.segment.header(name, default)

    def __getitem__(self, name):
        return self.segment[name]

    def __getattr__(self, name):
        return getattr(self.segment, name)

    async def __aenter__(self):
        return self

    async def __aexit__(self, **err):
        await self.close()

    def tell(self):
        """Return the number of bytes already consumed from the segment body."""
        return self.segment.size - len(self._buffer)

    async def read_chunk(self, limit=-1) -> bytes:
        """Read and return a single chunk of bytes from the segment body.

        If `limit` is negative or omitted, read and return a single chunk of data
        (up to :attr:`chunk_size <AsyncMultipartStreamParser.chunk_size>` bytes).
        This is the most efficient way of reading as it requires the least amount
        of copy operations or memory allocations.

        If `limit` is positive, return up to `limit` bytes and buffer any leftover
        bytes in memory for the next read operation. Fewer bytes may be returned if
        the current chunk or buffer is smaller than `limit`.

        At least one byte is returned, unless the part was already completely
        :attr:`consumed` or `limit` is `0`. Reading from a closed part is an error.

        :param limit: Maximum size of the returned chunk in bytes, or -1 for a
          full chunk.
        """

        if self.closed:
            raise ParserStateError("Multipart segment closed")

        if limit == 0:
            return b""

        if self._buffer:
            chunk = self._buffer
            self._buffer = b""
        elif self.consumed:
            return b""
        else:
            chunk = await anext(self._parser._events)
            if not chunk:
                self.consumed = True
                return b""
            assert isinstance(chunk, bytes)

        if 0 < limit < len(chunk):
            self._buffer = chunk[limit:]
            chunk = chunk[:limit]

        return chunk

    async def iter_chunks(self, maxread=-1):
        """Iterate over chunks of data by calling :meth:`read_chunk`
        in a loop.

        If `maxread` is negative (default), read until the end of the
        part. Otherwise, read up to `maxread` bytes in total.
        """
        if maxread < 0:
            while chunk := await self.read_chunk():
                yield chunk
        else:
            while chunk := await self.read_chunk(maxread):
                maxread -= len(chunk)
                yield chunk

    async def read(self, limit: int) -> bytes:
        """Read and return up to `limit` bytes, combining the results of multiple
        :meth:`read_chunk` calls if necessary. Only the very last read operation
        may return fewer bytes than requested.

        The `limit` parameter should be small enough to fit into memory at least
        twice. If you do not care about the exact size of a chunk of data, use
        the more efficient :meth:`read_chunk` method instead.
        """

        if limit < 0:
            raise AttributeError("Limit must not be negative")

        result = await self.read_chunk(limit)
        while len(result) < limit and not self.consumed:
            result += await self.read_chunk(limit - len(result))
        return result

    async def as_text(self, limit, encoding=None, trunk_ok=False) -> str:
        """Read and decode all remaining bytes into a unicode string,
        but fail with :exc:`ParserLimitReached` if this would require
        reading more than `limit` bytes.

        The `limit` is a safe-guard against accidentally reading very
        large parts into memory. If you are fine with partial results,
        set `trunk_ok` to `True`. Note that you risk :exc:`UnicodeDecodeError`
        if the data is truncated in the middle of a multi-byte unicode glyph.

        :param limit: Maximum number of bytes to read.
        :param encoding: If set, overrides the part header or parser defaults
          for text encoding.
        :param trunk_ok: If true, do not fail after `limit` bytes but
          instead return a partial result.
        """
        if limit < 0:
            raise AttributeError("Limit must not be negative")
        data = await self.read(limit)
        if not (trunk_ok or self.consumed):
            raise ParserLimitReached("Text field exceeds size limit")
        return data.decode(
            encoding or self.segment.charset or self._parser.text_charset
        )

    async def transfer(self, async_write: t_AsyncWriter, limit=-1):
        """Transfer up to `limit` bytes of data to an async write function
        and return the total number of bytes transferred.

        :param async_write: An async function that accepts a bytes object and
          returns the number of bytes written.
        :param limit: Maximum number of bytes to transfer.
        :return: Number of bytes transferred
        """
        total = 0
        async for chunk in self.iter_chunks(maxread=limit):
            n = await async_write(chunk)
            while n < len(chunk):
                n += await async_write(chunk[n:])
            total += n
        return total

    async def close(self):
        """Read and discard any remaining bytes from this part and mark it as closed.

        Parts are usually automatically closed by the :cls:`AsyncMultipartStreamParser`
        when requesting the next part or closing the parser. Reading from a closed part
        is an error."""
        if not self.closed:
            while not self.consumed:
                await self.read_chunk()
        self.closed = True
