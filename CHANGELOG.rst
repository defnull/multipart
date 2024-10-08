=========
Changelog
=========

Release 1.1
===========

This release could have been a patch release, but some of the fixes include
change in behavior to match documentation or specification. None of them should
be a surprise or have an impact on real-world clients, though. Existing apps
should be able to upgrade without issues.

* fix: Fail faster on input with invalid line breaks (#55)
* fix: Allow empty segment names (#56)
* fix: Avoid ResourceWarning when using parse_form_data (#57)
* fix: MultipartPart now always has a sensible content type.
* fix: Actually check parser state on context manager exit.
* fix: Honor Content-Length header, if present.
* perf: Reduce overhead for small segments (-21%)
* perf: Reduce write overhead for large uploads (-2%)

Release 1.0
===========

This release introduces a completely new, fast, non-blocking  ``PushMultipartParser``
parser, which now serves as the basis for all other parsers.

* feat: new ``PushMultipartParser`` parser.
* change: Parser is stricter by default and now rejects clearly broken input.
  This should not affect data sent by actual browsers or HTTP clients, but may break some artificial unit tests.
  * Fail on invalid line-breaks in headers or around boundaries.
  * Fail on invalid header names.
* change: Default charset for segment headers and text fields changed to ``utf8``, as recommended by W3C HTTP.
* change: Default disk and memory limits for ``MultipartParser`` increased, but multiple other limits were introduced to allow finer control. Check if the new defaults still fit your needs.
* change: Several undocumented APIs were deprecated or removed, some of which were not strictly private but should only be used by the parser itself, not by applications.

Release 0.2
===========

This release dropped support for Python versions below ``3.6``. Stay on ``multipart-0.1`` if you need Python 2.5+ support.

Patch 0.2.5
-----------

* security: Don't test semicolon separators in urlencoded data (#33)
* build: Add python-requires directive, indicating Python 3.5 or later is required and preventing older Pythons from attempting to download this version (#32)
* fix: Add official support for Python 3.10-3.12 (#38, #48)
* fix: Default value of ``copy_file`` should be ``2 ** 16``, not ``2 * 16`` (#41)
* docs: Update URL for Bottle (#42)

Patch 0.2.4
-----------

* fix: Consistently decode non-utf8 URL-encoded form-data

Patch 0.2.3
-----------

* fix: Import MutableMapping from collections.abc (#23)
* fix: Allow stream to contain data before first boundary (#25)
* tests: Fix a few more ResourceWarnings in the test suite (#24)

Patch 0.2.2
-----------

* fix: ResourceWarnings on Python 3 (#21)

Patch 0.2.1
-----------

* fix: empty payload (#20)


Release 0.1
===========

First release
