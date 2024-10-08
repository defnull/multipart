=========
Changelog
=========

Release 1.1
===========

Some of these fixes changed behavior to match documentation or specification, none of them should be a surprise. Existing apps should be able to upgrade without change.

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

This release introduces a completely new, fast, non-blocking  ``PushMultipartParser`` parser, which now serves as the basis for all other parsers.

* feat: ``PushMultipartParser`` parser
* change: Stricter parser rejects clearly broken input quicker, even in non-strict mode (e.g. invalid line breaks or header names). This should not affect data sent by actual browsers or HTTP clients.
* change: Default charset for ``MultipartParser`` headers and text fields changed to ``utf8``, as recommended by W3C HTTP.
* change: Default disk and memory limits for ``MultipartParser`` increased, but multiple other limits added for finer control. Check if the the new defaults still fit your needs.
* change: Undocumented APIs deprecated or removed, some of which were not strictly private. This includes parameters for ``MultipartParser`` and some ``MultipartPart`` methods, but those should not be used by anyone but the parser itself.

Release 0.2
===========

* change: Dropped support for Python versions below 3.6. Stay on 0.1 if you need Python 2.5+ support.

Patch 0.2.1
-----------

* fix: empty payload (#20)

Patch 0.2.2
-----------

* fix: ResourceWarnings on Python 3 (#21)

Patch 0.2.3
-----------

* fix: Import MutableMapping from collections.abc (#23)
* fix: Allow stream to contain data before first boundary (#25)
* tests: Fix a few more ResourceWarnings in the test suite (#24)

Patch 0.2.4
-----------

* dix: Consistently decode non-utf8 URL-encoded form-data

Patch 0.2.5
-----------

* security: Don't test semicolon separators in urlencoded data (#33)
* build: Add python-requires directive, indicating Python 3.5 or later is required and preventing older Pythons from attempting to download this version (#32)
* fix: Add official support for Python 3.10-3.12 (#38, #48)
* dix: Default value of ``copy_file`` should be ``2 ** 16``, not ``2 * 16`` (#41)
* docs: Update URL for Bottle (#42)


Release 0.1
===========

  * First release
