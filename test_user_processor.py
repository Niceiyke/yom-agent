"""Comprehensive unit tests for user_processor module using unittest."""

import unittest
from user_processor import process_user_data, is_valid_email


class TestIsValidEmail(unittest.TestCase):
    """Test cases for the is_valid_email helper function."""

    def test_valid_gmail_email(self):
        self.assertTrue(is_valid_email("user@gmail.com"))

    def test_valid_email_with_subdomain(self):
        self.assertTrue(is_valid_email("user@mail.example.com"))

    def test_valid_email_with_plus_sign(self):
        self.assertTrue(is_valid_email("user+tag@example.com"))

    def test_valid_email_with_dots(self):
        self.assertTrue(is_valid_email("first.last@example.com"))

    def test_valid_email_with_numbers(self):
        self.assertTrue(is_valid_email("user123@example.com"))

    def test_valid_email_uppercase(self):
        self.assertTrue(is_valid_email("USER@EXAMPLE.COM"))

    def test_valid_email_mixed_case_domain(self):
        self.assertTrue(is_valid_email("user@Example.Com"))

    def test_invalid_no_at_symbol(self):
        self.assertFalse(is_valid_email("userexample.com"))

    def test_invalid_no_domain(self):
        self.assertFalse(is_valid_email("user@"))

    def test_invalid_no_local_part(self):
        self.assertFalse(is_valid_email("@example.com"))

    def test_invalid_no_tld(self):
        self.assertFalse(is_valid_email("user@example"))

    def test_invalid_single_char_tld(self):
        self.assertFalse(is_valid_email("user@example.c"))

    def test_invalid_spaces(self):
        self.assertFalse(is_valid_email("user @example.com"))

    def test_invalid_empty_string(self):
        self.assertFalse(is_valid_email(""))

    def test_invalid_none(self):
        self.assertFalse(is_valid_email(None))

    def test_invalid_integer(self):
        self.assertFalse(is_valid_email(123))


class TestProcessUserData(unittest.TestCase):
    """Test cases for the main process_user_data function."""

    def test_all_valid_users(self):
        """When all users have valid emails, return all as valid."""
        users = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(invalid), 0)
        self.assertEqual(valid[0]["name"], "Alice")
        self.assertEqual(valid[1]["name"], "Bob")

    def test_all_invalid_users(self):
        """When all users have invalid emails, return all as invalid."""
        users = [
            {"name": "Alice", "email": "invalid-email"},
            {"name": "Bob", "email": "bob@"},
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 2)
        self.assertEqual(invalid, ["invalid-email", "bob@"])

    def test_mixed_valid_invalid_users(self):
        """When some users have valid emails and some don't."""
        users = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Bob", "email": "invalid-email"},
            {"name": "Carol", "email": "carol@test.org"},
            {"name": "Dave", "email": "dave@"},
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(invalid), 2)
        self.assertEqual(valid[0]["name"], "Alice")
        self.assertEqual(valid[1]["name"], "Carol")
        self.assertEqual(invalid, ["invalid-email", "dave@"])

    def test_empty_list(self):
        """When the input list is empty, return empty results."""
        valid, invalid = process_user_data([])
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 0)

    def test_user_missing_email(self):
        """User without email key should be treated as invalid."""
        users = [{"name": "Alice"}]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0], "")

    def test_user_with_empty_email(self):
        """User with empty email string should be treated as invalid."""
        users = [{"name": "Alice", "email": ""}]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)

    def test_user_with_none_email(self):
        """User with None email should be treated as invalid."""
        users = [{"name": "Alice", "email": None}]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)

    def test_user_with_additional_keys(self):
        """User dictionaries with extra keys should still be processed."""
        users = [
            {"name": "Alice", "email": "alice@example.com", "age": 30}
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["age"], 30)

    def test_preserves_original_user_dicts(self):
        """The function should not modify the original user dictionaries."""
        original_users = [{"name": "Alice", "email": "alice@example.com"}]
        users_copy = [{"name": "Alice", "email": "alice@example.com"}]
        
        process_user_data(original_users)
        
        self.assertEqual(original_users, users_copy)

    def test_invalid_input_not_a_list(self):
        """Should raise TypeError when input is not a list."""
        with self.assertRaises(TypeError) as context:
            process_user_data("not a list")
        self.assertIn("Expected list", str(context.exception))

    def test_invalid_input_dict(self):
        """Should raise TypeError when input is a dictionary."""
        with self.assertRaises(TypeError) as context:
            process_user_data({"name": "Alice"})
        self.assertIn("Expected list", str(context.exception))

    def test_invalid_user_entry_not_a_dict(self):
        """Should raise TypeError when a user entry is not a dictionary."""
        users = [{"name": "Alice", "email": "alice@example.com"}, "not a dict"]
        
        with self.assertRaises(TypeError) as context:
            process_user_data(users)
        self.assertIn("Expected dict", str(context.exception))

    def test_real_world_valid_emails(self):
        """Test with realistic email addresses."""
        users = [
            {"name": "John", "email": "john.doe@company.co.uk"},
            {"name": "Jane", "email": "jane+newsletter@example.org"},
            {"name": "Mike", "email": "mike123@sub.domain.com"},
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 3)
        self.assertEqual(len(invalid), 0)

    def test_edge_case_at_symbol_only(self):
        """Email with just @ should be invalid."""
        users = [{"name": "Alice", "email": "@"}]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)

    def test_edge_case_multiple_at_symbols(self):
        """Email with multiple @ symbols should be invalid."""
        users = [{"name": "Alice", "email": "a@b@c.com"}]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 1)

    def test_special_characters_in_email(self):
        """Emails with special characters should be validated correctly."""
        users = [
            {"name": "Alice", "email": "alice@example.com"},      # valid
            {"name": "Bob", "email": "bob@example.c"},             # invalid - single char TLD
        ]
        valid, invalid = process_user_data(users)
        
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)


if __name__ == "__main__":
    unittest.main()