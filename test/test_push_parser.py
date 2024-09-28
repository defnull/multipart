# -*- coding: utf-8 -*-
from contextlib import contextmanager
import unittest
import multipart as mp


def assertStrict(text):
    def decorator(func):
        def wrapper(self):
            func(self, strict=False)
            with self.assertRaisesRegex(mp.MultipartError, text):
                func(self, strict=True)

        return wrapper

    return decorator


class TestPushParser(unittest.TestCase):

    def setUp(self):
        self.reset(boundary="boundary")
        self.parts = []

    @contextmanager
    def assertMPE(self, text):
        with self.assertRaises(mp.MultipartError) as r:
            yield
        fullmsg = " ".join(map(str, r.exception.args))
        self.assertTrue(text in fullmsg, f"{text!r} not in {fullmsg!r}")

    def reset(self, **ka):
        ka.setdefault("boundary", "boundary")
        self.parser = mp.PushMultipartParser(**ka)
        self.parts = []

    def parse(self, data):
        self.parts = list(self.parser.parse(data))
        return self.parts

    def test_data_after_terminator(self):
        self.parse(b"--boundary--")
        self.parse(b"junk")  # Fine

        self.reset(strict=True)
        self.parse(b"--boundary--")
        with self.assertRaises(mp.MultipartError):
            self.parse(b"junk")

    def test_eof_before_clen(self):
        self.reset(content_length=100)
        self.parse(b"--boundary")
        with self.assertMPE("Unexpected end of multipart stream (parser closed)"):
            self.parse(b"")

    def test_data_after_eof(self):
        self.parse(b"--boundary--")
        assert self.parser._state == mp._COMPLETE
        assert not self.parser.closed

        self.parse(b"")
        assert self.parser.closed

        with self.assertMPE("Parser closed"):
            self.parse(b"junk")

    def test_eof_before_terminator(self):
        self.parse(b"--boundary")
        with self.assertMPE("Unexpected end of multipart stream"):
            self.parse(b"")

    def test_data_after_clen(self):
        self.reset(content_length=12)
        with self.assertMPE("Content-Length limit exceeded"):
            self.parse(b"--boundary\r\njunk")

    def test_clen_match(self):
        self.reset(content_length=12)
        self.parse(b"--boundary--")
        assert self.parser._state is mp._COMPLETE

    @assertStrict("Unexpected data in front of first delimiter")
    def test_junk_before(self, strict):
        self.reset(strict=strict)
        self.parse(b"junk--boundary--")

    @assertStrict("Unexpected data after end of multipart stream")
    def test_junk_after(self, strict):
        self.reset(strict=strict)
        self.parse(b"--boundary--")
        self.parse(b"junk")

    def test_close_before_end(self):
        self.parse(b"--boundary")
        with self.assertMPE("Unexpected end of multipart stream"):
            self.parser.close()

    def test_invalid_NL_delimiter(self):
        with self.assertMPE("Invalid line break after delimiter"):
            self.parse(b"--boundary\n")

    def test_invalid_NL_header(self):
        with self.assertMPE("Invalid line break in segment header"):
            self.parse(b"--boundary\r\nfoo:bar\nbar:baz")

    def test_header_size_limit(self):
        self.reset(max_header_size=1024)
        self.parse(b"--boundary\r\n")
        with self.assertMPE("Maximum segment header length exceeded"):
            self.parse(b"Header: " + b"x" * (1024))

        self.reset(max_header_size=1024, strict=True)
        self.parse(b"--boundary\r\n")
        with self.assertRaisesRegex(
            mp.MultipartError, "Maximum segment header length exceeded"
        ):
            self.parse(b"Header: " + b"x" * (1024) + b"\r\n")

    def test_header_count_limit(self):
        self.reset(max_header_count=10)
        self.parse(b"--boundary\r\n")
        for i in range(10):
            self.parse(b"Header: value\r\n")
        with self.assertMPE("Maximum segment header count exceeded"):
            self.parse(b"Header: value\r\n")

    @assertStrict("Unexpected segment header continuation")
    def test_header_continuation(self, strict):
        self.reset(strict=strict)
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data;\r\n")
        self.parse(b'\tname="foo"\r\n')
        parts = self.parse(b"\r\ndata\r\n--boundary--")
        self.assertEqual(
            [("Content-Disposition", 'form-data; name="foo"')], parts[0].headerlist
        )
        self.assertEqual(b"data", parts[1])

    def test_header_continuation_first(self):
        self.parse(b"--boundary\r\n")
        with self.assertMPE("Unexpected segment header continuation"):
            self.parse(b"\tbad: header\r\n\r\ndata\r\n--boundary--")

    def test_header_continuation_long(self):
        self.reset(max_header_size=1024)
        self.parse(b"--boundary\r\n")
        self.parse(b"Header: " + b"v" * 1000 + b"\r\n")
        with self.assertMPE("Maximum segment header length exceeded"):
            self.parse(b"\tmoooooooooooooooooooooooooore value\r\n")

    def test_header_bad_name(self):
        self.reset()
        with self.assertMPE("Malformed segment header"):
            self.parse(b"--boundary\r\nno-colon\r\n\r\ndata\r\n--boundary--")
        self.reset()
        with self.assertMPE("Malformed segment header"):
            self.parse(b"--boundary\r\n:empty-name\r\n\r\ndata\r\n--boundary--")
        for badchar in (b" ", b"\0", b"\r", b"\n", "ö".encode("utf8")):
            self.reset()
            with self.assertMPE("Invalid segment header name"):
                self.parse(
                    b"--boundary\r\ninvalid%sname:value\r\n\r\ndata\r\n--boundary--"
                    % badchar
                )
        self.reset()
        with self.assertMPE("Segment header failed to decode"):
            self.parse(
                b"--boundary\r\ninvalid\xc3\x28:value\r\n\r\ndata\r\n--boundary--"
            )

    def test_header_wrong_segment_subtype(self):
        with self.assertMPE("Invalid Content-Disposition segment header: Wrong type"):
            self.parse(
                b"--boundary\r\nContent-Disposition: mixed\r\n\r\ndata\r\n--boundary--"
            )

    def test_segment_empty_name(self):
        self.parse(b"--boundary\r\n")
        parts = self.parse(b"Content-Disposition: form-data; name\r\n\r\n")
        self.assertEqual(parts[0].name, "")
        self.parse(b"\r\n--boundary\r\n")
        parts = self.parse(b"Content-Disposition: form-data; name=\r\n\r\n")
        self.assertEqual(parts[0].name, "")
        self.parse(b"\r\n--boundary\r\n")
        parts = self.parse(b'Content-Disposition: form-data; name=""\r\n\r\n')
        self.assertEqual(parts[0].name, "")

    @assertStrict("Invalid Content-Disposition segment header: Missing name option")
    def test_segment_missing_name(self, strict):
        self.reset(strict=strict)
        self.parse(b"--boundary\r\n")
        parts = self.parse(b"Content-Disposition: form-data;\r\n\r\n")
        print(parts)
        self.assertEqual(parts[0].name, "")

    def test_segment_count_limit(self):
        self.reset(max_segment_count=1)
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo\r\n")
        self.parse(b"\r\n")
        with self.assertMPE("Maximum segment count exceeded"):
            self.parse(b"\r\n--boundary\r\n")

    def test_segment_size_limit(self):
        self.reset(max_segment_size=5)
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo\r\n")
        self.parse(b"\r\n")
        with self.assertMPE("Maximum segment size exceeded"):
            self.parse(b"123456")
            self.parse(b"\r\n--boundary\r\n")

    def test_partial_parts(self):
        self.reset()
        self.assertEqual([], self.parse(b"--boundary\r\n"))
        self.assertEqual(
            [], self.parse(b'Content-Disposition: form-data; name="foo"\r\n')
        )
        part = self.parse(b"\r\n")[0]
        self.assertEqual(
            [("Content-Disposition", 'form-data; name="foo"')], part.headerlist
        )
        # Write enough body data to trigger a new part
        part = self.parse(b"body" * 10)[0]
        # Write partial boundary, should stay incomplete
        part = self.parse(b"more\r\n--boundary")[0]
        # Turn the incomplete boundary into a terminator
        parts = self.parse(b"--")
        self.assertIsNone(parts[-1])

    def test_segment_clen(self):
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo\r\n")
        self.parse(b"Content-Length: 10\r\n")
        self.parse(b"\r\n")
        self.parse(b"x" * 10)
        self.parse(b"\r\n--boundary--")

    def test_segment_clen_exceeded(self):
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo\r\n")
        self.parse(b"Content-Length: 10\r\n")
        self.parse(b"\r\n")
        with self.assertMPE("Segment Content-Length exceeded"):
            self.parse(b"x" * 11)
            self.parse(b"\r\n--boundary--")

    def test_segment_clen_not_reached(self):
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo\r\n")
        self.parse(b"Content-Length: 10\r\n")
        self.parse(b"\r\n")
        with self.assertMPE("Segment size does not match Content-Length header"):
            self.parse(b"x" * 9)
            self.parse(b"\r\n--boundary--")

    def test_segment_handle_access(self):
        self.parse(b"--boundary\r\n")
        self.parse(b"Content-Disposition: form-data; name=foo; filename=bar.txt\r\n")
        self.parse(b"Content-Type: text/x-foo; charset=ascii\r\n")
        part = self.parse(b"\r\n")[0]
        self.assertEqual(
            part.header("Content-Disposition"), "form-data; name=foo; filename=bar.txt"
        )
        self.assertEqual(
            part.header("CONTENT-Disposition"), "form-data; name=foo; filename=bar.txt"
        )
        self.assertEqual(
            part["Content-Disposition"], "form-data; name=foo; filename=bar.txt"
        )
        self.assertEqual(
            part["CONTENT-Disposition"], "form-data; name=foo; filename=bar.txt"
        )
        self.assertEqual(part.name, "foo")
        self.assertEqual(part.filename, "bar.txt")
        with self.assertRaises(KeyError):
            part["Missing"]

