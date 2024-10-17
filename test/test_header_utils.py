# -*- coding: utf-8 -*-
import unittest
import multipart
import pytest

class TestHeaderParser(unittest.TestCase):

    def test_token_unquote(self):
        with pytest.deprecated_call():
            unquote = multipart.header_unquote
            self.assertEqual('foo', unquote('"foo"'))
            self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
            self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
            self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

        unquote = multipart.content_disposition_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

    def test_token_quote(self):
        with pytest.deprecated_call():
            quote = multipart.header_quote
            self.assertEqual(quote('foo'), 'foo')
            self.assertEqual(quote('foo"bar'), '"foo\\"bar"')

        quote = multipart.content_disposition_quote
        self.assertEqual(quote('foo'), '"foo"')
        self.assertEqual(quote('foo"bar'), '"foo%22bar"')

    def test_options_parser(self):
        parse = multipart.parse_options_header
        head = 'form-data; name="Test"; '
        self.assertEqual(parse(head+'filename="Test.txt"')[0], 'form-data')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['name'], 'Test')
        self.assertEqual(parse(head+'filename="Test.txt"')[1]['filename'], 'Test.txt')
        self.assertEqual(parse(head+'FileName="Te\\"st.txt"')[1]['filename'], 'Te"st.txt')
        self.assertEqual(parse(head+'filename="C:\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="\\\\test\\bla.txt"')[1]['filename'], 'bla.txt')
