import unittest,json
from unittest.mock import patch
import numpy as np
from partition_rom.core import load,evaluate
from site_agent.agent import SiteSafetyAgent,collect,parse_plan,fingerprint
from site_agent.client import DeepSeekClient,LLMError
class Fake:
    def __init__(self,route):self.route=route;self.calls=[]
    def complete(self,messages,json_mode=False):
        self.calls.append(messages)
        return json.dumps(self.route) if json_mode else '测试回答：根据[E1]。'
class Checks(unittest.TestCase):
    def setUp(self):
        self.m,self.report=load()
        self.s={'plan':[{'minute':0,'A':1.,'B':1.},{'minute':30,'A':1.2,'B':1.}],
            'watch':.2,'alarm':.5,'selected_minute':30.,'validation':self.report['validation'],
            'model_sha256':'test','geometry_sha256':self.report['geometry_sha256']}
    def test_route(self):
        for raw in ['{}','null','{"intent":"shell"}','{"intent":"compare","fraction":2}','{"intent":"element","element":true}']:
            with self.assertRaises(LLMError):parse_plan(raw)
    def test_compare(self):
        e=collect(self.m,self.s,{'intent':'compare','fraction':.5})
        self.assertAlmostEqual(e['candidate_summary'][-1]['max_change_mpa'],e['summary'][-1]['max_change_mpa']/2,places=9)
        self.assertEqual(self.s['plan'][-1]['A'],1.2)
    def test_element(self):
        e=collect(self.m,self.s,{'intent':'element','element':2081})
        self.assertEqual(len(e['element_history']),4)
        self.assertEqual(e['element_history'][0]['delta_mpa'],0)
    def test_missing_fraction(self):
        e=collect(self.m,self.s,{'intent':'compare','fraction':None})
        self.assertIn('clarification',e);self.assertNotIn('candidate_summary',e)
    def test_two_calls_and_history(self):
        f=Fake({'intent':'warning'});a=SiteSafetyAgent(f,self.m)
        out=a.answer('为什么？',self.s,[{'role':'user','content':'刚才的计划'}])
        self.assertEqual(len(f.calls),2);self.assertIn('刚才的计划',str(f.calls))
        self.assertIn('summary',out['evidence']);self.assertIn('summary',f.calls[-1][-1]['content'])
    def test_invalid_snapshot(self):
        f=Fake({'intent':'warning'});out=SiteSafetyAgent(f,self.m).answer('预警？',None)
        self.assertIn('error',out['evidence']);self.assertNotIn('summary',out['evidence'])
    def test_snapshot_change(self):
        old=fingerprint(self.s);self.s['watch']=.1;self.assertNotEqual(old,fingerprint(self.s))
    def test_transport(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'ok'}}]}).encode()
        with patch('urllib.request.build_opener') as b:
            b.return_value.open.return_value=Response()
            self.assertEqual(DeepSeekClient('test-only','test-model','https://example.test/v1').complete([{'role':'user','content':'你好'}]),'ok')
            req=b.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://example.test/v1/chat/completions')
            self.assertEqual(json.loads(req.data)['messages'][0]['content'],'你好')
    def test_no_secret_error(self):
        with patch('urllib.request.build_opener',side_effect=RuntimeError('SECRET')):
            with self.assertRaises(LLMError) as c:DeepSeekClient('SECRET','model','https://example.test').complete([])
            self.assertNotIn('SECRET',str(c.exception))
    def test_https_required(self):
        with self.assertRaises(LLMError):DeepSeekClient('test','model','http://example.test')
if __name__=='__main__':unittest.main()
