import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from app.storage import UserStorage


class UserStorageTest(unittest.TestCase):
    def test_api_key_round_trip_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "test.db")
            storage = UserStorage(database, Fernet.generate_key().decode())
            storage.initialize()

            storage.save_api_key(42, "secret-api-key")
            self.assertEqual(storage.get_api_key(42), "secret-api-key")

            storage.delete_api_key(42)
            self.assertIsNone(storage.get_api_key(42))

    def test_moderation_draft_can_only_be_signed_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "test.db")
            storage = UserStorage(database, Fernet.generate_key().decode())
            storage.initialize()

            token = storage.create_moderation_draft(
                42, {"operation": "PRODUCT_MODERATION", "tnved": "8509400000", "gtin": "4780172600012"}
            )
            self.assertEqual(storage.get_moderation_draft(token)["status"], "PENDING")
            self.assertTrue(storage.sign_moderation_draft(token, "x" * 200))
            self.assertFalse(storage.sign_moderation_draft(token, "y" * 200))
            self.assertEqual(storage.get_moderation_draft(token)["status"], "SIGNED")

    def test_business_place_id_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = UserStorage(
                str(Path(directory) / "test.db"), Fernet.generate_key().decode()
            )
            storage.initialize()
            storage.save_business_place_id(42, 27)
            self.assertEqual(storage.get_business_place_id(42), 27)


if __name__ == "__main__":
    unittest.main()
