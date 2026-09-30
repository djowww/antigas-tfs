import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from staging_safety import pin_staging_rsa_public, require_staging_target, rsa_public_modulus


class StagingSafetyTests(unittest.TestCase):
    def valid_env(self, **overrides):
        env = {
            "ANTIGAS_ALLOW_STAGING_MUTATIONS": "1",
            "TFS_DB_NAME": "antigas_world_test",
            "ANTIGAS_STAGING_GAME_PORT": "7176",
        }
        env.update(overrides)
        return env

    def test_accepts_explicit_test_target(self):
        self.assertEqual(require_staging_target(self.valid_env()), ("antigas_world_test", 7176))

    def test_accepts_qa_database_and_secondary_staging_port(self):
        env = self.valid_env(TFS_DB_NAME="antigas_market_qa", ANTIGAS_STAGING_GAME_PORT="7186")
        self.assertEqual(require_staging_target(env), ("antigas_market_qa", 7186))

    def test_requires_explicit_mutation_approval(self):
        env = self.valid_env(ANTIGAS_ALLOW_STAGING_MUTATIONS="")
        with self.assertRaises(SystemExit):
            require_staging_target(env)

    def test_rejects_unmarked_database(self):
        env = self.valid_env(TFS_DB_NAME="imperium")
        with self.assertRaises(SystemExit):
            require_staging_target(env)

    def test_rejects_production_token_even_with_test_suffix(self):
        env = self.valid_env(TFS_DB_NAME="antigas_production_test")
        with self.assertRaises(SystemExit):
            require_staging_target(env)

    def test_rejects_production_port(self):
        env = self.valid_env(ANTIGAS_STAGING_GAME_PORT="7174")
        with self.assertRaises(SystemExit):
            require_staging_target(env)

    def test_rejects_invalid_database_characters(self):
        env = self.valid_env(TFS_DB_NAME="antigas;drop_test")
        with self.assertRaises(SystemExit):
            require_staging_target(env)

    def test_staging_runner_pins_and_uses_staging_rsa_key(self):
        modulus = (1 << 1023) + 12345
        with TemporaryDirectory(prefix="antigas-stage-rsa-") as directory:
            path = Path(directory) / "staging-rsa-public.json"
            path.write_text(json.dumps({"modulus": str(modulus)}), encoding="utf-8")
            env = {}
            self.assertEqual(pin_staging_rsa_public(env, path), path)
            self.assertEqual(env["ANTIGAS_RSA_PUBLIC"], str(path))
            self.assertEqual(rsa_public_modulus(env), modulus)

    def test_staging_runner_rejects_a_missing_rsa_public_key(self):
        with TemporaryDirectory(prefix="antigas-stage-rsa-") as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaises(SystemExit):
                pin_staging_rsa_public({}, missing)


if __name__ == "__main__":
    unittest.main()
