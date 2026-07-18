# -*- coding: utf-8 -*-
import functools
import unittest
import multipart


class TestHeaderParser(unittest.TestCase):

    def test_token_unquote(self):
        unquote = multipart.header_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

        unquote = multipart.content_disposition_unquote
        self.assertEqual('foo', unquote('"foo"'))
        self.assertEqual('foo"bar', unquote('foo%22bar'))
        self.assertEqual('foo"bar', unquote('"foo%22bar"'))
        self.assertEqual('foo"bar', unquote('"foo\\"bar"'))
        self.assertEqual('ie.exe', unquote('"\\\\network\\ie.exe"', True))
        self.assertEqual('ie.exe', unquote('"c:\\wondows\\ie.exe"', True))

    def test_token_quote(self):
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
        self.assertEqual(parse(head+'FileName="Te\\"s\\\\t.txt"')[1]['filename'], 'Te"s\\t.txt')
        self.assertEqual(parse(head+'filename="C:\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="\\\\test\\bla.txt"')[1]['filename'], 'bla.txt')
        self.assertEqual(parse(head+'filename="täst.txt"')[1]['filename'], 'täst.txt')

        parse = functools.partial(multipart.parse_options_header, unquote=multipart.content_disposition_unquote)
        self.assertEqual(parse(head+'FileName="Te%22s\\\\t.txt"')[1]['filename'], 'Te"s\\\\t.txt')

    def test_content_disposition_parser(self):
        parse = multipart.parse_content_disposition

        self.assertEqual(parse('form-data; name="field"'), ('form-data', 'field', None))
        self.assertEqual(parse('form-data; name=""'), ('form-data', '', None))
        self.assertEqual(
            parse('form-data; name="file"; filename="test.txt"'),
            ('form-data', 'file', 'test.txt'),
        )
        self.assertEqual(
            parse('form-data; name="file"; filename=""'),
            ('form-data', 'file', ''),
        )

        self.assertEqual(parse('form-data; name="a%22b"'), ('form-data', 'a"b', None))
        self.assertEqual(
            parse('form-data; name="a%0Db%0Ac"'),
            ('form-data', 'a\rb\nc', None),
        )
        self.assertEqual(
            parse('form-data; name="file"; filename="a%22b.txt"'),
            ('form-data', 'file', 'a"b.txt'),
        )

        self.assertEqual(
            parse('form-data; filename="test.txt"; name="field"'),
            ('form-data', 'field', 'test.txt'),
        )
        self.assertEqual(parse('FORM-DATA; name="field"'), ('form-data', 'field', None))
        self.assertEqual(parse('form-data ; name="field"'), ('form-data', 'field', None))
        self.assertEqual(parse('form-data; name=field'), ('form-data', 'field', None))
        self.assertEqual(parse('form-data; name="a\\"b"'), ('form-data', 'a"b', None))
        self.assertEqual(
            parse('form-data; name="file"; filename="C:\\fakepath\\test.txt"'),
            ('form-data', 'file', 'test.txt'),
        )
