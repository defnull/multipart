# -*- coding: utf-8 -*-
"""
This module provides multiple parsers for RFC-7578 `multipart/form-data`,
both low-level for framework authors and high-level for WSGI application
developers.

Copyright (c) 2010-2024, Marcel Hellkamp
License: MIT (see LICENSE file)
"""


__author__ = "Marcel Hellkamp"
__version__ = '1.2.0-dev'
__license__ = "MIT"
__all__ = ["MultipartError", "ParserLimitReached", "ParserError",
           "ParserWarning", "ParserClosedError", "is_form_request",
           "parse_form_data", "MultipartParser", "MultipartPart",
           "PushMultipartParser", "MultipartSegment"]


import re
from io import BytesIO
from typing import Iterator, Union, Optional, Tuple, List
from urllib.parse import parse_qs
from wsgiref.headers import Headers
from collections.abc import MutableMapping as DictMixin
import tempfile
import functools


##
### Exceptions
##


class MultipartError(ValueError):
    """ Base class for all parser errors or warnings """


class ParserLimitReached(MultipartError):
    """ Parser reached one of the configured limits """


class ParserError(MultipartError):
    """ Detected invalid, inconsistent or incomplete input """


class ParserWarning(ParserError):
    """ Detected unusual input while parsing in strict mode """


class ParserClosedError(MultipartError):
    """ Parser received data after beeing closed """


##############################################################################
################################ Helper & Misc ###############################
##############################################################################
# Some of these were copied from bottle: https://bottlepy.org


class MultiDict(DictMixin):
    """ A dict that stores multiple values per key. Most dict methods return the
        last value by default. There are special methods to get all values.
    """

    def __init__(self, *args, **kwargs):
        self.dict = {}
        for arg in args:
            if hasattr(arg, 'items'):
                for k, v in arg.items():
                    self[k] = v
            else:
                for k, v in arg:
                    self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def __len__(self):
        return len(self.dict)

    def __iter__(self):
        return iter(self.dict)

    def __contains__(self, key):
        return key in self.dict

    def __delitem__(self, key):
        del self.dict[key]

    def __str__(self):
        return str(self.dict)

    def __repr__(self):
        return repr(self.dict)

    def keys(self):
        return self.dict.keys()

    def __getitem__(self, key):
        return self.get(key, KeyError, -1)

    def __setitem__(self, key, value):
        self.append(key, value)

    def append(self, key, value):
        self.dict.setdefault(key, []).append(value)

    def replace(self, key, value):
        self.dict[key] = [value]

    def getall(self, key):
        return self.dict.get(key) or []

    def get(self, key, default=None, index=-1):
        if key not in self.dict and default != KeyError:
            return [default][index]

        return self.dict[key][index]

    def iterallitems(self):
        """ Yield (key, value) keys, but for all values. """
        for key, values in self.dict.items():
            for value in values:
                yield key, value


def to_bytes(data, enc="utf8"):
    if isinstance(data, str):
        data = data.encode(enc)

    return data


def copy_file(stream, target, maxread=-1, buffer_size=2 ** 16):
    """ Read from :stream and write to :target until :maxread or EOF. """
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)


class _cached_property:
    """ A property that is only computed once per instance and then replaces
        itself with an ordinary attribute. Deleting the attribute resets the
        property. """

    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func

    def __get__(self, obj, cls):
        if obj is None: return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


# -------------
# Header Parser
# -------------


# ASCII minus control or special chars
_token="[a-zA-Z0-9-!#$%&'*+.^_`|~]+" 
_re_istoken = re.compile("^%s$" % _token, re.ASCII)
# A token or quoted-string (simple qs | token | slow qs)
_value = r'"[^\\"]*"|%s|"(?:\\.|[^"])*"' % _token
# A "; key=value" pair from content-disposition header
_option = r'; *(%s) *= *(%s)' % (_token, _value)
_re_option = re.compile(_option)

def header_quote(val):
    if _re_istoken.match(val):
        return val

    return '"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'


def header_unquote(val, filename=False):
    if val[0] == val[-1] == '"':
        val = val[1:-1]

        # fix ie6 bug: full path --> filename
        if filename and (val[1:3] == ":\\" or val[:2] == "\\\\"):
            val = val.split("\\")[-1]

        return val.replace("\\\\", "\\").replace('\\"', '"')

    return val


def parse_options_header(header, options=None):
    i = header.find(";")
    if i < 0:
        return header.lower().strip(), {}

    options = options or {}
    for key, val in _re_option.findall(header, i):
        key = key.lower()
        options[key] = header_unquote(val, key == "filename")

    return header[:i].lower().strip(), options


##############################################################################
################################## SansIO Parser #############################
##############################################################################


# Parser states as constants
_PREAMBLE = "PREAMBLE"
_HEADER = "HEADER"
_BODY = "BODY"
_COMPLETE = "END"


class PushMultipartParser:
    def __init__(
        self,
        boundary: Union[str, bytes],
        content_length=-1,
        max_header_size=4096 + 128,  # 4KB should be enough for everyone
        max_header_count=8,  # RFC 7578 allows just 3
        max_segment_size=2**64,  # Practically unlimited
        max_segment_count=2**64,  # Practically unlimited
        header_charset="utf8",
        strict=False,
    ):
        """A push-based (incremental, non-blocking) parser for multipart/form-data.

        In `strict` mode, the parser will be less forgiving and bail out more
        quickly when presented with strange or invalid input, avoiding
        unnecessary work caused by broken or malicious clients. Fatal errors
        will always trigger exceptions, even in non-strict mode.

        The various limits are meant as safeguards and exceeding any of those
        limit will trigger a :exc:`ParserLimitReached` exception.

        :param boundary: The multipart boundary as found in the Content-Type header.
        :param content_length: Maximum number of bytes to parse, or -1 for no limit.
        :param max_header_size: Maximum size of a single header (name+value).
        :param max_header_count: Maximum number of headers per segment.
        :param max_segment_size: Maximum size of a single segment.
        :param max_segment_count: Maximum number of segments.
        :param header_charset: Charset for header names and values.
        :param strict: Enables additional format and sanity checks.
        """
        self.boundary = to_bytes(boundary)
        self.content_length = content_length
        self.header_charset = header_charset
        self.max_header_size = max_header_size
        self.max_header_count = max_header_count
        self.max_segment_size = max_segment_size
        self.max_segment_count = max_segment_count
        self.strict = strict

        self._delimiter = b"--" + self.boundary

        # Internal parser state
        self._parsed = 0
        self._fieldcount = 0
        self._buffer = bytearray()
        self._current = None
        self._state = _PREAMBLE

        #: True if the parser was closed.
        self.closed = False
        #: The last error
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(check_complete=not exc_type)

    def parse(
        self, chunk: Union[bytes, bytearray]
    ) -> Iterator[Union["MultipartSegment", bytearray, None]]:
        """Parse a chunk of data and yield as many result objects as possible
        with the data given.

        For each multipart segment, the parser will emit a single instance
        of :class:`MultipartSegment` with all headers already present,
        followed by zero or more non-empty `bytearray` instances containing
        parts of the segment body, followed by a single `None` signaling the
        end of the segment.

        The returned iterator will stop if more data is required or if the end
        of the multipart stream was detected. The iterator must be fully consumed
        before parsing the next chunk. End of input can be signaled by parsing
        an empty chunk or closing the parser. This is important to verify the
        multipart message was parsed completely and the last segment is actually
        complete.

        Format errors or exceeded limits will trigger :exc:`MultipartError`.
        """

        try:
            assert isinstance(chunk, (bytes, bytearray))

            if not chunk:
                self.close()
                return

            if self.closed:
                raise ParserClosedError("Parser closed")

            if self.content_length > -1 and self.content_length < self._parsed + len(
                self._buffer
            ) + len(chunk):
                raise ParserError("Content-Length limit exceeded")

            if self._state is _COMPLETE:
                if self.strict:
                    raise ParserWarning("Unexpected data after end of multipart stream")
                return

            buffer = self._buffer
            delimiter = self._delimiter
            buffer += chunk  # Copy chunk to existing buffer
            offset = 0
            d_len = len(delimiter)
            bufferlen = len(buffer)

            while True:

                # Scan for first delimiter
                if self._state is _PREAMBLE:
                    index = buffer.find(delimiter, offset)

                    if (index == -1 or index > offset) and self.strict:
                        # Data before the first delimiter is allowed (RFC 2046,
                        # section 5.1.1) but very uncommon.
                        raise ParserWarning("Unexpected data in front of first delimiter")

                    if index > -1:
                        tail = buffer[index + d_len : index + d_len + 2]

                        # First delimiter found -> Start after it
                        if tail == b"\r\n":
                            self._current = MultipartSegment(self)
                            self._state = _HEADER
                            offset = index + d_len + 2
                            continue

                        # First delimiter is terminator -> Empty multipart stream
                        if tail == b"--":
                            offset = index + d_len + 2
                            self._state = _COMPLETE
                            break  # parsing complete

                        # Bad newline after valid delimiter -> Broken client
                        if tail and tail[0:1] == b"\n":
                            raise ParserError("Invalid line break after delimiter")

                    # Delimiter not found, skip data until we find one
                    offset = bufferlen - (d_len + 4)
                    break  # wait for more data

                # Parse header section
                elif self._state is _HEADER:
                    nl = buffer.find(b"\r\n", offset)

                    if nl > offset:  # Non-empty header line
                        self._current._add_headerline(buffer[offset:nl])
                        offset = nl + 2
                        continue
                    elif nl == offset:  # Empty header line -> End of header section
                        self._current._close_headers()
                        yield self._current
                        self._state = _BODY
                        offset += 2
                        continue
                    else:  # No CRLF found -> Ask for more data
                        if buffer.find(b"\n", offset) != -1:
                            raise ParserError("Invalid line break in segment header")
                        if bufferlen - offset > self.max_header_size:
                            raise ParserLimitReached("Maximum segment header length exceeded")
                        break  # wait for more data

                # Parse body until next delimiter is found
                elif self._state is _BODY:
                    index = buffer.find(b"\r\n" + delimiter, offset)
                    tail = index > -1 and buffer[index + d_len + 2 : index + d_len + 4]

                    if tail in (b"\r\n", b"--"):  # Delimiter or terminator found
                        if index > offset:
                            self._current._update_size(index - offset)
                            yield buffer[offset:index]
                        offset = index + d_len + 4
                        self._current._mark_complete()
                        yield None

                        if tail == b"--":  # Delimiter was a terminator
                            self._state = _COMPLETE
                            break

                        # Normal delimiter, continue with next segment
                        self._current = MultipartSegment(self)
                        self._state = _HEADER
                        continue

                    # No delimiter or terminator found
                    min_keep = d_len + 3
                    chunk = buffer[offset:-min_keep]
                    if chunk:
                        self._current._update_size(len(chunk))
                        offset += len(chunk)
                        yield chunk
                    break  # wait for more data

                else:  # pragma: no cover
                    raise RuntimeError(f"Unexpected internal state: {self._state}")

            # We ran out of data, or reached the end
            self._parsed += offset
            buffer[:] = buffer[offset:]
        except Exception as err:
            if not self.error:
                self.error = err
            self.close(check_complete=False)
            raise

    def close(self, check_complete=True):
        """
        Close this parser if not already closed.

        :param check_complete: Raise MultipartError if the parser did not
            reach the end of the multipart stream yet.
        """

        self.closed = True
        self._current = None
        del self._buffer[:]

        if check_complete and not self._state is _COMPLETE:
            err = ParserError("Unexpected end of multipart stream (parser closed)")
            if not self.error:
                self.error = err
            raise err


class MultipartSegment:

    #: List of headers as name/value pairs with normalized (Title-Case) names.
    headerlist: List[Tuple[str, str]]
    #: The 'name' option of the Content-Disposition header. Always a string,
    #: but may be empty.
    name: str
    #: The optional 'filename' option of the Content-Disposition header.
    filename: Optional[str]
    #: The Content-Type of this segment, if the header was present.
    #: Not the entire header, just the actual content type without options.
    content_type: Optional[str]
    #: The 'charset' option of the Content-Type header, if present.
    charset: Optional[str]

    #: Segment body size (so far). Will be updated during parsing.
    size: int
    #: If true, the last chunk of segment body data was parsed and the size
    #: value is final.
    complete: bool

    def __init__(self, parser: PushMultipartParser):
        """ MultipartSegments are created by the PushMultipartParser and
        represent a single multipart segment, but do not store or buffer any
        of the content. The parser will emit MultipartSegments with a fully
        populated headerlist and derived information (name, filename, ...) can
        be accessed.
        """
        self._parser = parser

        if parser._fieldcount+1 > parser.max_segment_count:
            raise ParserLimitReached("Maximum segment count exceeded")
        parser._fieldcount += 1

        self.headerlist = []
        self.size = 0
        self.complete = 0

        self.name = None
        self.filename = None
        self.content_type = None
        self.charset = None
        self._clen = -1
        self._size_limit = parser.max_segment_size

    def _add_headerline(self, line: bytearray):
        assert line and self.name is None
        parser = self._parser

        if line[0] in b" \t":  # Multi-line header value
            if not self.headerlist or parser.strict:
                raise ParserWarning("Unexpected segment header continuation")
            prev = ": ".join(self.headerlist.pop())
            line = prev.encode(parser.header_charset) + b" " + line.strip()

        if len(line) > parser.max_header_size:
            raise ParserLimitReached("Maximum segment header length exceeded")
        if len(self.headerlist) >= parser.max_header_count:
            raise ParserLimitReached("Maximum segment header count exceeded")

        try:
            name, col, value = line.decode(parser.header_charset).partition(":")
            name = name.strip()
            if not col or not name:
                raise ParserError("Malformed segment header")
            if " " in name or not name.isascii() or not name.isprintable():
                raise ParserError("Invalid segment header name")
        except UnicodeDecodeError as err:
            raise ParserError("Segment header failed to decode", err)

        self.headerlist.append((name.title(), value.strip()))

    def _close_headers(self):
        assert self.name is None

        for h,v in self.headerlist:
            if h == "Content-Disposition":
                dtype, args = parse_options_header(v)
                if dtype != "form-data":
                    raise ParserError("Invalid Content-Disposition segment header: Wrong type")
                if "name" not in args and self._parser.strict:
                    raise ParserWarning("Invalid Content-Disposition segment header: Missing name option")
                self.name = args.get("name", "")
                self.filename = args.get("filename")
            elif h == "Content-Type":
                self.content_type, args = parse_options_header(v)
                self.charset = args.get("charset")
            elif h == "Content-Length" and v.isdecimal():
                self._clen = int(v)

        if self.name is None:
            raise ParserError("Missing Content-Disposition segment header")

    def _update_size(self, bytecount: int):
        assert self.name is not None and not self.complete
        self.size += bytecount
        if self._clen >= 0 and self.size > self._clen:
            raise ParserError("Segment Content-Length exceeded")
        if self.size > self._size_limit:
            raise ParserLimitReached("Maximum segment size exceeded")

    def _mark_complete(self):
        assert self.name is not None and not self.complete
        if self._clen >= 0 and self.size != self._clen:
            raise ParserError("Segment size does not match Content-Length header")
        self.complete = True

    def header(self, name: str, default=None):
        """Return the value of a header if present, or a default value."""
        compare = name.title()
        for header in self.headerlist:
            if header[0] == compare:
                return header[1]
        if default is KeyError:
            raise KeyError(name)
        return default

    def __getitem__(self, name):
        """Return a header value if present, or raise KeyError."""
        return self.header(name, KeyError)


##############################################################################
################################## Multipart #################################
##############################################################################


class MultipartParser(object):
    def __init__(
        self,
        stream,
        boundary,
        content_length=-1,
        charset="utf8",
        strict=False,
        buffer_size=1024 * 64,
        header_limit=8,
        headersize_limit=1024 * 4 + 128,  # 4KB
        part_limit=128,
        partsize_limit=2**64,  # practically unlimited
        spool_limit=1024 * 64,  # Keep fields up to 64KB in memory
        memory_limit=1024 * 64 * 128,  # spool_limit * part_limit
        disk_limit=2**64,  # practically unlimited
        mem_limit=0,
        memfile_limit=0,
    ):
        """A parser that reads from a multipart/form-data encoded byte stream
        and yields :class:`MultipartPart` instances.

        The parse itself is an iterator and will read and parse data on
        demand. results are cached, so once fully parsed, it can be iterated
        over again.

        :param stream: A readable byte stream. Must implement ``.read(size)``.
        :param boundary: The multipart boundary as found in the Content-Type header.
        :param content_length: The maximum number of bytes to read.
        :param charset: Default charset for headers and text fields.
        :param strict: Enables additional format and sanity checks.
        :param buffer_size: Size of chunks read from the source stream

        :param header_limit: Maximum number of headers per segment
        :param headersize_limit: Maximum size of a segment header line
        :param part_limit: Maximum number of segments to parse
        :param partsize_limit: Maximum size of a segment body
        :param spool_limit: Segments up to this size are buffered in memory,
            larger segments are buffered in temporary files on disk.
        :param memory_limit: Maximum size of all memory-buffered segments.
        :param disk_limit: Maximum size of all disk-buffered segments

        :param memfile_limit: Deprecated alias for `spool_limit`.
        :param mem_limit: Deprecated alias for `memory_limit`.
        """
        self.stream = stream
        self.boundary = boundary
        self.content_length = content_length
        self.charset = charset
        self.strict = strict
        self.buffer_size = buffer_size
        self.header_limit = header_limit
        self.headersize_limit = headersize_limit
        self.part_limit = part_limit
        self.partsize_limit = partsize_limit
        self.memory_limit = mem_limit or memory_limit
        self.spool_limit = min(memfile_limit or spool_limit, self.memory_limit)
        self.disk_limit = disk_limit

        self._done = []
        self._part_iter = None

    def __iter__(self):
        """Iterate over the parts of the multipart message."""
        if not self._part_iter:
            self._part_iter = self._iterparse()

        if self._done:
            yield from self._done

        for part in self._part_iter:
            self._done.append(part)
            yield part

    def parts(self):
        """Returns a list with all parts of the multipart message."""
        return list(self)

    def get(self, name, default=None):
        """Return the first part with that name or a default value."""
        for part in self:
            if name == part.name:
                return part

        return default

    def get_all(self, name):
        """Return a list of parts with that name."""
        return [p for p in self if p.name == name]

    def _iterparse(self):
        read = self.stream.read
        bufsize = self.buffer_size
        mem_used = disk_used = 0
        readlimit = self.content_length

        part = None
        parser = PushMultipartParser(
            boundary=self.boundary,
            content_length=self.content_length,
            max_header_count=self.header_limit,
            max_header_size=self.headersize_limit,
            max_segment_count=self.part_limit,
            max_segment_size=self.partsize_limit,
            header_charset=self.charset,
        )

        with parser:
            while not parser.closed:

                if readlimit >= 0:
                    chunk = read(min(bufsize, readlimit))
                    readlimit -= len(chunk)
                else:
                    chunk = read(bufsize)

                for event in parser.parse(chunk):
                    if isinstance(event, MultipartSegment):
                        part = MultipartPart(
                            buffer_size=self.buffer_size,
                            memfile_limit=self.spool_limit,
                            charset=self.charset,
                            segment=event,
                        )
                    elif event:
                        part._write(event)
                        if part.is_buffered():
                            if part.size + mem_used > self.memory_limit:
                                raise ParserLimitReached("Memory limit reached")
                        elif part.size + disk_used > self.disk_limit:
                            raise ParserLimitReached("Disk limit reached")
                    else:
                        if part.is_buffered():
                            mem_used += part.size
                        else:
                            disk_used += part.size
                        part._mark_complete()
                        yield part
                        part = None


class MultipartPart(object):
    def __init__(
        self,
        buffer_size=2**16,
        memfile_limit=2**18,
        charset="utf8",
        segment: "MultipartSegment" = None,
    ):
        self._segment = segment
        #: A file-like object holding the fields content
        self.file = BytesIO()
        self.size = 0
        self.name = segment.name
        self.filename = segment.filename
        #: Charset as defined in the segment header, or the parser default charset
        self.charset = segment.charset or charset
        self.headerlist = segment.headerlist

        self.memfile_limit = memfile_limit
        self.buffer_size = buffer_size

    @_cached_property
    def headers(self) -> Headers:
        return Headers(self._segment.headerlist)

    @_cached_property
    def disposition(self) -> str:
        return self._segment.header("Content-Disposition")

    @_cached_property
    def content_type(self) -> str:
        return self._segment.content_type or (
            "application/octet-stream" if self.filename else "text/plain")

    def _write(self, chunk):
        self.size += len(chunk)
        self.file.write(chunk)
        if self.size > self.memfile_limit:
            old = self.file
            self.file = tempfile.TemporaryFile()
            self.file.write(old.getvalue())
            self._write = self._write_nocheck

    def _write_nocheck(self, chunk):
        self.size += len(chunk)
        self.file.write(chunk)

    def _mark_complete(self):
        self.file.seek(0)

    def is_buffered(self):
        """Return true if the data is fully buffered in memory."""
        return isinstance(self.file, BytesIO)

    @property
    def value(self):
        """Return the entire payload as decoded text.

        Warning, this may consume a lot of memory, check size first.
        """

        return self.raw.decode(self.charset)

    @property
    def raw(self):
        """Return the entire payload as a raw byte string.

        Warning, this may consume a lot of memory, check size first.
        """
        pos = self.file.tell()
        self.file.seek(0)

        val = self.file.read()
        self.file.seek(pos)
        return val

    def save_as(self, path):
        """Save a copy of this part to `path` and return its size."""
        with open(path, "wb") as fp:
            pos = self.file.tell()
            try:
                self.file.seek(0)
                size = copy_file(self.file, fp, buffer_size=self.buffer_size)
            finally:
                self.file.seek(pos)
        return size

    def close(self):
        if self.file:
            self.file.close()
            self.file = False


##############################################################################
#################################### WSGI ####################################
##############################################################################


def is_form_request(environ):
    """ Return True if the environ represents a form request that can be parsed
        with :func:`parse_form_data`. Checks for a compatible `Content-Type`
        header.
    """

    content_type = environ.get("CONTENT_TYPE", "")
    return content_type.split(";", 1)[0].strip().lower() in (
        "multipart/form-data",
        "application/x-www-form-urlencoded",
        "application/x-url-encoded"
    )


def parse_form_data(
        environ,
        charset="utf8",
        strict=False,
        ignore_errors=None,
        **kwargs):
    """ Parses both types of form data (multipart and url-encoded) from a WSGI
        environment and returns two :class:`MultiDict` instances, one for
        text form fields (strings) and one for file uploads (:class:`MultipartPart`
        instances). Text fields that are too big to fit into memory limits are
        treated as file uploads with no filename.

        In case of an url-encoded form request, the total request body size is
        limited by `memory_limit`. Larger requests will trigger an error. 

        :param environ: A WSGI environment dictionary. Only `wsgi.input`,
            `CONTENT_TYPE` and `CONTENT_LENGTH` are used. 
        :param charset: The default charset used to decode headers and text fields.
        :param strict: Enables additional format and sanity checks.
        :param ignore_errors: If True, all errors are silently ignored and the
            returned results may be empty or incomplete. If False, raised
            exceptions are propagated to teh caller. If None (default) exceptions
            are propagated in strict mode but ignored in non-strict mode.
        :param **kwargs: Additional keyword arguments are forwarded to
            :class:`MultipartParser`. This is particularly useful to change the
            default parser limits.
        :raises MultipartError: See `ignore_errors` parameters. 
    """

    forms, files = MultiDict(), MultiDict()

    try:
        stream = environ.get("wsgi.input")
        if not stream:
            if strict:
                raise ParserWarning("No 'wsgi.input' in environment.")
            stream = BytesIO()

        content_type = environ.get("CONTENT_TYPE", "")
        if not content_type:
            if strict:
                raise ParserWarning("Missing Content-Type header")
            return forms, files

        try:
            content_length = int(environ.get("CONTENT_LENGTH", "-1"))
        except ValueError:
            raise ParserError("Invalid Content-Length header")

        content_type, options = parse_options_header(content_type)
        kwargs["charset"] = charset = options.get("charset", charset)

        if content_type == "multipart/form-data":
            boundary = options.get("boundary", "")

            if not boundary:
                raise ParserError("Missing boundary for multipart/form-data")

            for part in MultipartParser(stream, boundary, content_length, **kwargs):
                if part.filename or not part.is_buffered():
                    files.append(part.name, part)
                else:  # TODO: Big form-fields go into the files dict. Really?
                    forms.append(part.name, part.value)
                    part.close()

        elif content_type in (
            "application/x-www-form-urlencoded",
            "application/x-url-encoded",
        ):
            mem_limit = kwargs.get("memory_limit", kwargs.get("mem_limit", 1024*64*128))
            if content_length > -1:
                if content_length > mem_limit:
                    raise ParserLimitReached("Memory limit exceeded")
                data = stream.read(min(mem_limit, content_length))
                if len(data) < content_length:
                    raise ParserError("Unexpected end of data stream")
            else:
                data = stream.read(mem_limit + 1)
                if len(data) > mem_limit:
                    raise ParserLimitReached("Memory limit exceeded")

            data = data.decode(charset)
            data = parse_qs(data, keep_blank_values=True, encoding=charset)

            for key, values in data.items():
                for value in values:
                    forms.append(key, value)
        elif strict:
            raise ParserWarning("Unsupported Content-Type")

    except MultipartError:
        if ignore_errors is None:
            ignore_errors = not strict
        if not ignore_errors:
            for _, part in files.iterallitems():
                part.close()
            raise

    return forms, files
