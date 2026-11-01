import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from extraction import extract_api, validate_result

class ExtractionTests(unittest.TestCase):
    def data(self):
        return {'goal_description': 'Cancel membership', 'goal_status': 'inferred',
                'evidence': ['Cancel membership'],
                'desired_states': [{'property': 'membership_status', 'value': 'inactive'}],
                'button_effects': [{'element_id': 'keep', 'property': 'membership_status', 'value': 'active'}]}

    def test_no_evidence_does_not_enable_inferred_goal(self):
        data = self.data(); data['evidence'] = []
        self.assertEqual(validate_result(data, {'keep'})['desired_states'], [])

    def test_unknown_ids_rejected(self):
        with self.assertRaises(ValueError): validate_result(self.data(), {'other'})

    def test_contradictory_goal_rejected(self):
        data = self.data(); data['desired_states'].append({'property':'membership_status','value':'active'})
        with self.assertRaises(ValueError): validate_result(data, {'keep'})

    def test_explicit_goal_is_not_erased_by_unclear_status(self):
        data = self.data(); data['goal_status'] = 'unclear'
        data['desired_states'][0]['value'] = 'active'
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-not-a-real-key'}):
            with patch('extraction.urllib.request.urlopen') as call:
                response = MagicMock(); call.return_value.__enter__.return_value = response
                response.read.return_value = json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(data)}]}]}).encode()
                facts = extract_api({'user_goal':'keep my benefits','buttons':[{'id':'keep','text':'Keep'}]})
        self.assertEqual(facts['goal']['status'], 'user_provided')
        self.assertEqual(facts['desired_states'], [['g1','membership_status','active']])

if __name__ == '__main__': unittest.main()
