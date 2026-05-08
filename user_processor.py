"""User data processing module with email validation."""

import re
from typing import Dict, List, Tuple


# RFC 5322 compliant email regex pattern
# This pattern covers most valid email formats
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def is_valid_email(email: str) -> bool:
    """Validate an email address using regex pattern.
    
    Args:
        email: The email address string to validate.
        
    Returns:
        True if the email is valid, False otherwise.
    """
    if not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email))


def process_user_data(users: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str]]:
    """Process a list of user dictionaries and validate email addresses.
    
    Args:
        users: List of dictionaries, each containing 'name' and 'email' keys.
        
    Returns:
        A tuple containing:
            - List of valid user dictionaries (with properly formatted emails)
            - List of invalid email addresses found in the input
            
    Raises:
        TypeError: If users is not a list or if user entries are not dictionaries.
        
    Examples:
        >>> users = [
        ...     {'name': 'John Doe', 'email': 'john@example.com'},
        ...     {'name': 'Jane Smith', 'email': 'jane@example.com'}
        ... ]
        >>> valid, invalid = process_user_data(users)
        >>> len(valid)
        2
        >>> len(invalid)
        0
    """
    if not isinstance(users, list):
        raise TypeError(f"Expected list, got {type(users).__name__}")
    
    valid_users: List[Dict[str, str]] = []
    invalid_emails: List[str] = []
    
    for user in users:
        if not isinstance(user, dict):
            raise TypeError(f"Expected dict, got {type(user).__name__}")
        
        # Extract email, default to empty string if missing
        email = user.get('email', '')
        
        if is_valid_email(email):
            valid_users.append(user)
        else:
            invalid_emails.append(email)
    
    return valid_users, invalid_emails