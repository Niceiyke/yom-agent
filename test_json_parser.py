"""Tests for the JSON parser."""

import pytest
from json_parser import JSONParser, JSONParseError, loads


class TestParseSimpleValues:
    def test_parse_null(self):
        assert loads("null") is None
    
    def test_parse_true(self):
        assert loads("true") is True
    
    def test_parse_false(self):
        assert loads("false") is False
    
    def test_parse_positive_integer(self):
        assert loads("42") == 42
    
    def test_parse_negative_integer(self):
        assert loads("-42") == -42
    
    def test_parse_positive_float(self):
        assert loads("3.14") == 3.14
    
    def test_parse_negative_float(self):
        assert loads("-3.14") == -3.14
    
    def test_parse_exponent_number(self):
        assert loads("1.5e10") == 1.5e10


class TestParseStrings:
    def test_empty_string(self):
        assert loads('""') == ""
    
    def test_simple_string(self):
        assert loads('"hello"') == "hello"
    
    def test_string_with_spaces(self):
        assert loads('"hello world"') == "hello world"
    
    def test_escaped_quote(self):
        assert loads('"hello\\"world"') == 'hello"world'
    
    def test_escaped_backslash(self):
        assert loads('"hello\\\\world"') == "hello\\world"
    
    def test_escaped_newline(self):
        assert loads('"hello\\nworld"') == "hello\nworld"
    
    def test_escaped_tab(self):
        assert loads('"hello\\tworld"') == "hello\tworld"
    
    def test_unicode_escape(self):
        assert loads('"\\u0048\\u0065\\u006C\\u006C\\u006F"') == "Hello"
    
    def test_string_with_unicode(self):
        assert loads('"你好"') == "你好"


class TestParseArrays:
    def test_empty_array(self):
        assert loads("[]") == []
    
    def test_single_element_array(self):
        assert loads("[1]") == [1]
    
    def test_multiple_element_array(self):
        assert loads('[1, 2, 3]') == [1, 2, 3]
    
    def test_mixed_types_array(self):
        assert loads('[1, "hello", true, null]') == [1, "hello", True, None]
    
    def test_nested_array(self):
        assert loads('[[1, 2], [3, 4]]') == [[1, 2], [3, 4]]


class TestParseObjects:
    def test_empty_object(self):
        assert loads("{}") == {}
    
    def test_single_property(self):
        assert loads('{"name": "Alice"}') == {"name": "Alice"}
    
    def test_multiple_properties(self):
        result = loads('{"name": "Alice", "age": 30}')
        assert result == {"name": "Alice", "age": 30}
    
    def test_nested_object(self):
        result = loads('{"person": {"name": "Alice"}}')
        assert result == {"person": {"name": "Alice"}}


class TestParseComplexJSON:
    def test_complex_nested(self):
        json_str = '''
        {
            "name": "Alice",
            "age": 30,
            "addresses": [
                {"city": "NYC", "zip": "10001"},
                {"city": "LA", "zip": "90001"}
            ],
            "active": true
        }
        '''
        result = loads(json_str)
        assert result["name"] == "Alice"
        assert result["age"] == 30
        assert len(result["addresses"]) == 2
        assert result["active"] is True


class TestErrorHandling:
    def test_invalid_json_empty_string(self):
        with pytest.raises(JSONParseError):
            loads("")
    
    def test_invalid_json_unclosed_object(self):
        with pytest.raises(JSONParseError):
            loads('{"name": "Alice"')
    
    def test_invalid_json_unclosed_array(self):
        with pytest.raises(JSONParseError):
            loads('[1, 2, 3')
    
    def test_invalid_json_missing_colon(self):
        with pytest.raises(JSONParseError):
            loads('{"name" "Alice"}')
    
    def test_invalid_json_trailing_comma(self):
        with pytest.raises(JSONParseError):
            loads('[1, 2, 3,]')
    
    def test_invalid_json_invalid_escape(self):
        with pytest.raises(JSONParseError):
            loads('"\\q"')
    
    def test_invalid_json_invalid_control_char(self):
        with pytest.raises(JSONParseError):
            loads('"\n"')
    
    def test_error_message_contains_position(self):
        try:
            loads('{"name": invalid}')
        except JSONParseError as e:
            assert "position" in str(e).lower()


class TestWhitespaceHandling:
    def test_whitespace_before(self):
        assert loads('   42') == 42
    
    def test_whitespace_after(self):
        assert loads('42   ') == 42
    
    def test_whitespace_around_colon(self):
        assert loads('{"name" : "Alice"}') == {"name": "Alice"}
    
    def test_whitespace_around_comma(self):
        assert loads('[1 , 2 , 3]') == [1, 2, 3]