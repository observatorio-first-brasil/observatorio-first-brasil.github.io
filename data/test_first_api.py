import unittest

from . import first_api


class FirstAvatarParsing(unittest.TestCase):
    def test_lowercase_response(self):
        row = first_api._avatar_record(
            {"teams": [{"teamNumber": 1156, "encodedAvatar": "abc"}]}, 1156)
        self.assertEqual(row["encodedAvatar"], "abc")

    def test_uppercase_response(self):
        row = first_api._avatar_record(
            {"Teams": [{"TeamNumber": 7563, "Avatar": "xyz"}]}, 7563)
        self.assertEqual(row["Avatar"], "xyz")

    def test_wrong_team_is_ignored(self):
        self.assertIsNone(first_api._avatar_record(
            {"teams": [{"teamNumber": 1156}, {"teamNumber": 7563}]}, 9999))


if __name__ == "__main__":
    unittest.main()
