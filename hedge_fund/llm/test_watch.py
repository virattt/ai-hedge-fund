"""Reading a half-written answer.

The live run board is only worth watching if the verdict lands before the
prose — and only safe if a partial decode never shows something the finished
parse would contradict. Both are tested here at every chunk boundary that
matters.
"""

from __future__ import annotations

from hedge_fund.llm.watch import ThesisStream

ANSWER = (
    '{"signal": "bearish", "confidence": 78, '
    '"reasoning": "The multiple prices in a decade of flawless execution."}'
)


def feed_char_by_char(text: str) -> ThesisStream:
    """The worst case a provider can hand us: one character per chunk."""
    stream = ThesisStream()
    for char in text:
        stream.feed(char)
    return stream


class TestOrder:
    """Agents answer signal, then confidence, then reasoning."""

    def test_verdict_lands_before_the_thesis(self):
        stream = ThesisStream()
        stream.feed('{"signal": "bullish", "confidence": 90, "reasoning": "A wo')
        assert stream.verdict() == "BULLISH 90%"
        assert stream.thesis == "A wo"

    def test_signal_shows_before_confidence_arrives(self):
        stream = ThesisStream()
        stream.feed('{"signal": "bearish", "confi')
        assert stream.verdict() == "BEARISH"
        assert stream.confidence is None

    def test_confidence_waits_for_its_terminator(self):
        """A half-written 78 must never be read as 7 — the number would tick
        down on screen and read as the agent changing its mind."""
        stream = ThesisStream()
        stream.feed('{"signal": "bullish", "confidence": 7')
        assert stream.confidence is None
        stream.feed('8,')
        assert stream.confidence == 78.0

    def test_nothing_decodable_yet(self):
        stream = ThesisStream()
        stream.feed('{"sig')
        assert stream.verdict() is None
        assert stream.thesis == ""


class TestChunking:
    """Chunk boundaries are the provider's business, never the view's."""

    def test_one_character_at_a_time_matches_one_shot(self):
        whole = ThesisStream()
        whole.feed(ANSWER)
        piecemeal = feed_char_by_char(ANSWER)
        assert (piecemeal.signal, piecemeal.confidence, piecemeal.thesis) == (
            whole.signal, whole.confidence, whole.thesis)

    def test_thesis_only_grows(self):
        """It types out — it never rewinds, which would look like a glitch."""
        stream = ThesisStream()
        seen = ""
        for char in ANSWER:
            stream.feed(char)
            assert stream.thesis.startswith(seen)
            seen = stream.thesis
        assert seen == "The multiple prices in a decade of flawless execution."


class TestEscapes:
    def test_escaped_quote_is_not_the_end_of_the_thesis(self):
        stream = ThesisStream()
        stream.feed('{"reasoning": "He called it a \\"moat\\" business."}')
        assert stream.thesis == 'He called it a "moat" business.'

    def test_a_dangling_backslash_waits(self):
        """Half an escape is not yet a character; printing the backslash for a
        frame would be a visible wrong glyph."""
        stream = ThesisStream()
        stream.feed('{"reasoning": "up 20%\\')
        assert stream.thesis == "up 20%"
        stream.feed('n and holding"')
        assert stream.thesis == "up 20%\n and holding"

    def test_unicode_escape_waits_for_all_four_digits(self):
        stream = ThesisStream()
        stream.feed('{"reasoning": "P\\u00')
        assert stream.thesis == "P"
        stream.feed('e9rez"')
        assert stream.thesis == "Pérez"

    def test_malformed_unicode_escape_stops_rather_than_raises(self):
        """Best-effort by contract: the finished parse reports the error, the
        view just stops early instead of taking the run down with it."""
        stream = ThesisStream()
        stream.feed('{"reasoning": "bad \\uZZZZ here"')
        assert stream.thesis == "bad "


class TestOtherShapes:
    def test_prose_leaves_every_field_empty(self):
        stream = ThesisStream()
        stream.feed("I think this company is wonderful, and here is why.")
        assert stream.verdict() is None
        assert stream.thesis == ""

    def test_fenced_json_still_decodes(self):
        """extract_json accepts a ```json fence, so the stream must too."""
        stream = ThesisStream()
        stream.feed('```json\n{"signal": "neutral", "confidence": 50, ')
        assert stream.verdict() == "NEUTRAL 50%"

    def test_unknown_signal_word_is_shown_not_guessed(self):
        """The finished parse rejects it; until then, show what was said."""
        stream = ThesisStream()
        stream.feed('{"signal": "sideways"')
        assert stream.verdict() == "SIDEWAYS"
