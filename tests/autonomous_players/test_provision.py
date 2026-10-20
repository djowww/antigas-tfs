import tempfile
import unittest
from pathlib import Path
from tools.autonomous_players.provision import prepare_manifest, provision_sql
from tools.autonomous_players.provision import backup_database
from unittest.mock import patch


class ProvisionTests(unittest.TestCase):
    def test_failed_backup_cannot_leave_a_success_receipt(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'backup.sql'
            with patch('tools.autonomous_players.provision.subprocess.run',side_effect=subprocess.CalledProcessError(1,['mysqldump'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    backup_database('test_qa',path,'test-identity')
            self.assertFalse(path.exists())
            self.assertFalse(Path(str(path)+'.receipt.json').exists())
    def test_explicit_authorization_and_population_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.json'
            with self.assertRaises(ValueError):
                prepare_manifest(path,'world-identity',20,False)
            with self.assertRaises(ValueError):
                prepare_manifest(path,'world-identity',21,True)
            manifest = prepare_manifest(path,'world-identity',20,True)
            self.assertEqual(len(manifest['players']),20)
            self.assertEqual(len({p['account'] for p in manifest['players']}),20)
            self.assertEqual(prepare_manifest(path,'world-identity',20,True),manifest)
            with self.assertRaises(ValueError):
                prepare_manifest(path,'another-world',20,True)

    def test_only_inserts_normal_players_and_no_gameplay_values(self):
        with tempfile.TemporaryDirectory() as directory:
            m = prepare_manifest(Path(directory)/'manifest.json','identity',1,True)
            query = provision_sql(m,[])
            self.assertIn('START TRANSACTION;',query)
            self.assertIn('COMMIT;',query)
            self.assertNotIn('UPDATE ',query)
            self.assertNotIn('DELETE ',query)
            self.assertNotIn('premium_points',query)
            self.assertIn(",1,0,150,150,'',400,",query)
            self.assertNotIn('player_items',query)
            self.assertEqual(provision_sql(m,[m['players'][0]['account']]),'')
