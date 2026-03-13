from src.utils.llm import extract_json_from_response


def test_extract_json_from_raw_json():
    response = '{"signal":"bullish","confidence":0.82}'
    assert extract_json_from_response(response) == {"signal": "bullish", "confidence": 0.82}


def test_extract_json_from_fenced_json_block():
    response = """Here is the analysis:
```json
{"signal":"neutral","confidence":0.4}
```
"""
    assert extract_json_from_response(response) == {"signal": "neutral", "confidence": 0.4}


def test_extract_json_from_embedded_json_object():
    response = "Analysis complete: {\"signal\":\"bearish\",\"confidence\":0.2} end."
    assert extract_json_from_response(response) == {"signal": "bearish", "confidence": 0.2}


def test_extract_json_returns_none_when_not_parseable():
    assert extract_json_from_response("no structured output") is None
