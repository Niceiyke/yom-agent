"""Simple JSON parser implementation."""

from typing import Any, Dict, List, Union


class JSONParseError(Exception):
    """Custom exception for JSON parsing errors."""
    
    def __init__(self, message: str, position: int = 0):
        self.position = position
        super().__init__(f"{message} at position {position}")


class JSONParser:
    """A parser that converts JSON strings to Python objects."""
    
    def __init__(self, json_string: str):
        self.json_string = json_string
        self.pos = 0
        self.length = len(json_string)
    
    def parse(self) -> Union[Dict, List, str, int, float, bool, None]:
        """Parse the JSON string and return the Python object."""
        self.pos = 0
        self._skip_whitespace()
        
        if self.pos >= self.length:
            raise JSONParseError("Unexpected end of input", self.pos)
        
        result = self._parse_value()
        self._skip_whitespace()
        
        if self.pos < self.length:
            raise JSONParseError("Unexpected character after parsing", self.pos)
        
        return result
    
    def _peek(self) -> str:
        """Peek at the current character without advancing."""
        if self.pos < self.length:
            return self.json_string[self.pos]
        return ''
    
    def _consume(self) -> str:
        """Consume and return the current character."""
        if self.pos < self.length:
            char = self.json_string[self.pos]
            self.pos += 1
            return char
        return ''
    
    def _skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < self.length and self.json_string[self.pos] in ' \t\n\r':
            self.pos += 1
    
    def _parse_value(self) -> Any:
        """Parse any JSON value."""
        self._skip_whitespace()
        
        if self.pos >= self.length:
            raise JSONParseError("Unexpected end of input", self.pos)
        
        char = self.json_string[self.pos]
        
        if char == '{':
            return self._parse_object()
        elif char == '[':
            return self._parse_array()
        elif char == '"':
            return self._parse_string()
        elif char == '-' or char.isdigit():
            return self._parse_number()
        elif char == 't':
            return self._parse_literal("true", True)
        elif char == 'f':
            return self._parse_literal("false", False)
        elif char == 'n':
            return self._parse_literal("null", None)
        else:
            raise JSONParseError(f"Invalid character: '{char}'", self.pos)
    
    def _parse_object(self) -> Dict:
        """Parse a JSON object."""
        if self.json_string[self.pos] != '{':
            raise JSONParseError("Expected '{'", self.pos)
        
        self.pos += 1
        self._skip_whitespace()
        
        result: Dict[str, Any] = {}
        
        if self.pos < self.length and self.json_string[self.pos] == '}':
            self.pos += 1
            return result
        
        while True:
            self._skip_whitespace()
            
            if self.json_string[self.pos] != '"':
                raise JSONParseError("Expected property name in quotes", self.pos)
            
            key = self._parse_string()
            self._skip_whitespace()
            
            if self.pos >= self.length or self.json_string[self.pos] != ':':
                raise JSONParseError("Expected ':' after property name", self.pos)
            self.pos += 1
            
            self._skip_whitespace()
            value = self._parse_value()
            
            result[key] = value
            self._skip_whitespace()
            
            if self.pos >= self.length:
                raise JSONParseError("Unexpected end of input", self.pos)
            
            if self.json_string[self.pos] == '}':
                self.pos += 1
                break
            
            if self.json_string[self.pos] != ',':
                raise JSONParseError("Expected ',' or '}'", self.pos)
            self.pos += 1
        
        return result
    
    def _parse_array(self) -> List:
        """Parse a JSON array."""
        if self.json_string[self.pos] != '[':
            raise JSONParseError("Expected '['", self.pos)
        
        self.pos += 1
        self._skip_whitespace()
        
        result: List[Any] = []
        
        if self.pos < self.length and self.json_string[self.pos] == ']':
            self.pos += 1
            return result
        
        while True:
            self._skip_whitespace()
            value = self._parse_value()
            result.append(value)
            self._skip_whitespace()
            
            if self.pos >= self.length:
                raise JSONParseError("Unexpected end of input", self.pos)
            
            if self.json_string[self.pos] == ']':
                self.pos += 1
                break
            
            if self.json_string[self.pos] != ',':
                raise JSONParseError("Expected ',' or ']'", self.pos)
            self.pos += 1
        
        return result
    
    def _parse_string(self) -> str:
        """Parse a JSON string."""
        if self.json_string[self.pos] != '"':
            raise JSONParseError("Expected '\"'", self.pos)
        
        self.pos += 1
        result = []
        
        while self.pos < self.length:
            char = self.json_string[self.pos]
            
            if char == '"':
                self.pos += 1
                return ''.join(result)
            
            if char == '\\':
                self.pos += 1
                if self.pos >= self.length:
                    raise JSONParseError("Unterminated escape sequence", self.pos)
                
                escape_char = self.json_string[self.pos]
                
                if escape_char == '"':
                    result.append('"')
                elif escape_char == '\\':
                    result.append('\\')
                elif escape_char == '/':
                    result.append('/')
                elif escape_char == 'b':
                    result.append('\b')
                elif escape_char == 'f':
                    result.append('\f')
                elif escape_char == 'n':
                    result.append('\n')
                elif escape_char == 'r':
                    result.append('\r')
                elif escape_char == 't':
                    result.append('\t')
                elif escape_char == 'u':
                    self.pos += 1
                    if self.pos + 4 > self.length:
                        raise JSONParseError("Insufficient characters for unicode", self.pos)
                    hex_code = self.json_string[self.pos:self.pos + 4]
                    try:
                        result.append(chr(int(hex_code, 16)))
                    except ValueError:
                        raise JSONParseError(f"Invalid unicode: {hex_code}", self.pos)
                    self.pos += 3
                else:
                    raise JSONParseError(f"Invalid escape: '\\{escape_char}'", self.pos)
            elif char < ' ':
                raise JSONParseError(f"Invalid control character: {repr(char)}", self.pos)
            else:
                result.append(char)
            
            self.pos += 1
        
        raise JSONParseError("Unterminated string", self.pos)
    
    def _parse_number(self) -> Union[int, float]:
        """Parse a JSON number."""
        start = self.pos
        
        if self.json_string[self.pos] == '-':
            self.pos += 1
            if self.pos >= self.length or not self.json_string[self.pos].isdigit():
                raise JSONParseError("Invalid number format", start)
        
        # Integer part
        while self.pos < self.length and self.json_string[self.pos].isdigit():
            self.pos += 1
        
        # Decimal part
        if self.pos < self.length and self.json_string[self.pos] == '.':
            self.pos += 1
            if self.pos >= self.length or not self.json_string[self.pos].isdigit():
                raise JSONParseError("Invalid number format", start)
            while self.pos < self.length and self.json_string[self.pos].isdigit():
                self.pos += 1
        
        # Exponent part
        if self.pos < self.length and self.json_string[self.pos] in 'eE':
            self.pos += 1
            if self.pos < self.length and self.json_string[self.pos] in '+-':
                self.pos += 1
            if self.pos >= self.length or not self.json_string[self.pos].isdigit():
                raise JSONParseError("Invalid number format", start)
            while self.pos < self.length and self.json_string[self.pos].isdigit():
                self.pos += 1
        
        num_str = self.json_string[start:self.pos]
        
        try:
            if '.' not in num_str and 'e' not in num_str and 'E' not in num_str:
                return int(num_str)
            return float(num_str)
        except ValueError:
            raise JSONParseError(f"Invalid number: {num_str}", start)
    
    def _parse_literal(self, expected: str, value: Any) -> Any:
        """Parse a literal (true, false, null)."""
        end = self.pos + len(expected)
        if end > self.length or self.json_string[self.pos:end] != expected:
            raise JSONParseError(f"Expected {expected}", self.pos)
        self.pos = end
        return value


def loads(json_string: str) -> Union[Dict, List, str, int, float, bool, None]:
    """Parse a JSON string into a Python object."""
    parser = JSONParser(json_string)
    return parser.parse()