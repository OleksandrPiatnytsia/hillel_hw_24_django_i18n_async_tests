"""The translation files themselves: complete, compiled, consistent.

Catches the usual i18n mistakes before a person sees them on the site:
- a new text marked with _() / {% translate %}, but not translated in the
  uk .po (makemessages added it with an empty msgstr);
- a "fuzzy" entry: makemessages guessed it from a similar old text, and
  Django IGNORES fuzzy translations;
- the .po was changed, but compilemessages was not run: Django reads the
  .mo, so the site would still show the old text;
- a translation that lost or renamed a placeholder: "%(title)s" in English
  and "%(name)s" in Ukrainian -> KeyError when the text is formatted.
"""

import re
from pathlib import Path

import polib
from django.conf import settings

LOCALE = Path(settings.BASE_DIR) / "locale" / "uk" / "LC_MESSAGES"
PO = polib.pofile(str(LOCALE / "django.po"))
MO = polib.mofile(str(LOCALE / "django.mo"))

# %(name)s, %(count)d, %s ... and {size} (format_lazy)
PLACEHOLDER = re.compile(r"%\(\w+\)[sd]|%[sd]|\{\w+\}")


def translations(entry):
    """All msgstr of an entry: one, or one per plural form (uk has 4)."""
    return list(entry.msgstr_plural.values()) if entry.msgid_plural else [entry.msgstr]


def test_every_text_is_translated_and_not_fuzzy():
    untranslated = [entry.msgid for entry in PO if not entry.translated()]
    fuzzy = [entry.msgid for entry in PO.fuzzy_entries()]

    assert untranslated == []
    assert fuzzy == []


def test_ukrainian_has_four_plural_forms():
    # The CLDR rule of gettext for uk: one / few / many / other
    assert "nplurals=4" in PO.metadata["Plural-Forms"]
    for entry in PO:
        if entry.msgid_plural:
            assert len(entry.msgstr_plural) == 4, entry.msgid


def test_compiled_mo_matches_the_po():
    """compilemessages was run after the last change of the .po."""
    po = {(entry.msgctxt, entry.msgid): translations(entry) for entry in PO.translated_entries()}
    mo = {(entry.msgctxt, entry.msgid): translations(entry) for entry in MO}

    assert {key: value for key, value in mo.items() if key[1]} == po


def test_translations_keep_the_placeholders():
    broken = []
    for entry in PO.translated_entries():
        # Plural entries: compared with the plural msgid ("%(count)s books")
        expected = sorted(PLACEHOLDER.findall(entry.msgid_plural or entry.msgid))
        for text in translations(entry):
            if sorted(PLACEHOLDER.findall(text)) != expected:
                broken.append((entry.msgid, text))

    assert broken == []
