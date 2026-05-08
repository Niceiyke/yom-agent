def reverse_string(s):
    """Reverse a given string.
    
    Args:
        s: The input string to reverse.
        
    Returns:
        The reversed string.
    """
    return s[::-1]


# Example usage
if __name__ == "__main__":
    original = "Hello, World!"
    reversed_str = reverse_string(original)
    print(f"Original: {original}")
    print(f"Reversed: {reversed_str}")