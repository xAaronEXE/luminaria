import unittest
from datetime import date
from backend.usage import activity_grid,account_view
from backend.identity import validate_user

class ProfileTests(unittest.TestCase):
 def test_grid_has_53_aligned_weeks_and_distinguishes_unrecorded_and_future(self):
  result=activity_grid([{'day':'2026-10-20','metrics':{'tokens_in':20,'tokens_out':10}}],'2026-10-19','UTC',date(2026,10,21))
  self.assertEqual(len(result['cells']),371)
  self.assertEqual(date.fromisoformat(result['cells'][0]['day']).weekday(),0)
  rows={r['day']:r for r in result['cells']}
  self.assertIsNone(rows['2026-10-18']['tokens']);self.assertEqual(rows['2026-10-19']['tokens'],0)
  self.assertEqual(rows['2026-10-20']['tokens'],30);self.assertTrue(rows['2026-10-22']['future'])
 def test_empty_grid_is_not_fabricated_zeros(self):
  self.assertTrue(all(c['tokens'] is None for c in activity_grid([],None,'UTC',date(2026,10,21))['cells']))
 def test_account_streak_is_recomputed_for_today(self):
  source={'account_id':'a'*32,'devices':2,'days':[{'day':'2026-10-20','metrics':{'tokens_in':40,'tokens_out':2,'generations':1}}]}
  self.assertEqual(account_view(source,'UTC',date(2026,10,21))['streak']['current'],1)
  self.assertEqual(account_view(source,'UTC',date(2026,10,23))['streak']['current'],0)
  self.assertEqual(account_view(source)['total'],42)
 def test_username_is_not_an_email_or_markup(self):
  base={'id':'a'*32,'provider':'github','name':'Example'}
  self.assertEqual(validate_user({**base,'handle':'public-user'})['handle'],'public-user')
  for handle in ('person@example.com','<script>','x'*81):self.assertIsNone(validate_user({**base,'handle':handle})['handle'])

if __name__=='__main__':unittest.main()
