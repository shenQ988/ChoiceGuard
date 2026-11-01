import sys
import importlib.util
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
spec = importlib.util.spec_from_file_location('server', Path(__file__).resolve().parents[1] / 'backend/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class RulesTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('souffle'), 'Soufflé is not installed')
    def test_only_explicit_opposing_states_conflict(self):
        facts = {'desired_states': [['g1', 'membership_status', 'inactive']],
                 'button_effects': [['keep', 'membership_status', 'active'],
                                    ['cancel', 'membership_status', 'inactive'],
                                    ['next', 'membership_status', 'confirmation'],
                                    ['other', 'renewal', 'active']]}
        self.assertEqual(server.reason(facts), ['keep'])

    def test_demo_is_scoped_and_preserves_ids(self):
        facts = server.extract_facts({'mode': 'demo', 'url': 'http://127.0.0.1:8765/demo',
                                      'buttons': [{'id': 'unique-7', 'text': 'Keep my benefits'}]})
        self.assertEqual(facts['button_effects'][0][0], 'unique-7')
        with self.assertRaises(ValueError):
            server.extract_facts({'mode': 'demo', 'url': 'https://example.com'})

    def test_explicit_goal_bypasses_manual_demo(self):
        page = {'mode': 'demo', 'user_goal': 'keep my benefits'}
        with patch.object(server, 'extract_api', return_value={'live': True}) as api:
            self.assertEqual(server.extract_facts(page), {'live': True})
            api.assert_called_once_with(page)

    def test_tabs_in_facts_rejected(self):
        # Validation is performed before passing facts to the engine.
        if not shutil.which('souffle'):
            self.skipTest('Soufflé is not installed')
        with self.assertRaises(ValueError):
            server.reason({'desired_states': [['g', 'p', 'bad\tvalue']], 'button_effects': []})

if __name__ == '__main__': unittest.main()
