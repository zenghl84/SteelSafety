import unittest
import numpy as np
import pandas as pd
from partition_rom.core import load,predict,evaluate,read_case
class Checks(unittest.TestCase):
    def setUp(self):self.m,self.report=load()
    def test_holdouts(self):
        for a,b in [(0.9,1.1),(1.1,0.9)]:
            actual,_=read_case(a,b)
            self.assertLess(abs(predict(self.m,a,b)-actual.stress.to_numpy()).max(),.001)
    def test_domain(self):
        for a,b in [(1.2,1.2),(.8,.8),(float('nan'),1.)]:
            with self.assertRaises(ValueError):predict(self.m,a,b)
    def test_plan_baseline_and_thresholds(self):
        p=pd.DataFrame({'minute':[0,10,30],'A':[1,1.1,1.2],'B':[1,1,1]})
        s,f,d=evaluate(self.m,p,.1,.2)
        np.testing.assert_array_equal(d[0],np.zeros(len(d[0])))
        np.testing.assert_allclose(d[2],f[2]-f[0])
        self.assertEqual(s.status.iloc[0],'未触发');self.assertEqual(s.status.iloc[-1],'报警')
        p['A']=1
        self.assertTrue((evaluate(self.m,p,.1,.2)[0].status=='未触发').all())
    def test_bad_plan(self):
        for times in [[1,10],[0,0],[0,31]]:
            with self.assertRaises(ValueError):evaluate(self.m,pd.DataFrame({'minute':times,'A':[1,1],'B':[1,1]}),1,2)
    def test_threshold_equality(self):
        p=pd.DataFrame({'minute':[0,30],'A':[1,1.2],'B':[1,1]})
        peak=evaluate(self.m,p,1,100)[0].max_change_mpa.iloc[-1]
        self.assertEqual(evaluate(self.m,p,peak/2,peak)[0].status.iloc[-1],'报警')
if __name__=='__main__':unittest.main()
