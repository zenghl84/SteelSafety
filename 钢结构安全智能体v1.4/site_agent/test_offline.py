import unittest
from unittest.mock import patch
from site_agent.offline import OfflineSiteAgent,route_question
from site_agent.test_agent import Checks
from partition_rom.core import load
class OfflineChecks(unittest.TestCase):
    def setUp(self):
        c=Checks();c.setUp();self.s=c.s;self.agent=OfflineSiteAgent(c.m)
    def test_no_api(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
            a=self.agent.answer('分析当前计划',self.s)
        self.assertIn('summary',a['evidence']);self.assertIn('MPa',a['answer'])
    def test_percent(self):
        self.assertEqual(route_question('减少20%的加载进度')['fraction'],.8)
        self.assertEqual(route_question('加载进度降低到20%')['fraction'],.2)
        self.assertEqual(route_question('保留80%的加载进度')['fraction'],.8)
    def test_compare(self):
        e=self.agent.answer('加载进度减半',self.s)['evidence']
        self.assertAlmostEqual(e['candidate_summary'][-1]['max_change_mpa'],e['summary'][-1]['max_change_mpa']/2)
    def test_followup(self):
        a=self.agent.answer('查询杆件2081',self.s)
        b=self.agent.answer('这根杆件呢',self.s,[a])
        self.assertEqual(b['route']['element'],2081)
    def test_unsupported(self):
        a=self.agent.answer('增加两吨材料安全吗',self.s)
        self.assertEqual(a['route']['topic'],'unsupported');self.assertNotIn('summary',a['evidence'])
    def test_unknown(self):
        a=self.agent.answer('推荐餐厅',self.s)
        self.assertIn('暂不支持',a['answer'])
    def test_invalid(self):
        self.assertIn('没有有效预测',self.agent.answer('分析当前计划',None)['answer'])
    def test_missing_ratio(self):
        self.assertIn('请说明',self.agent.answer('减少加载进度',self.s)['answer'])
    def test_emergency(self):
        self.assertIn('不等待',self.agent.answer('结构明显变形',None)['answer'])
if __name__=='__main__':unittest.main()
