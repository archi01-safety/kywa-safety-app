import json,subprocess,sys,tempfile,unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'tools'/'summarize-startup.py'

class MeasurementReportTest(unittest.TestCase):
    def run_report(self, samples, evidence):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'samples.json';proof=root/'proof.json';output=root/'report.json';config=root/'config.json'
            source.write_text(json.dumps({'target':'https://kywa-safety.onrender.com/healthz','samples':samples}),encoding='utf-8')
            proof.write_text(json.dumps(evidence),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--samples',str(source),'--evidence',str(proof),'--output',str(output),'--config',str(config)],capture_output=True,text=True)
            return result,json.loads(output.read_text()) if output.exists() else None,json.loads(config.read_text()) if config.exists() else None
    def sample(self, trial, seconds=30, kind='unconfirmed'):
        return {'trial':trial,'seconds':seconds,'kind':kind,'at':'2026-11-18T15:00:00+09:00'}
    def proof(self, trial, verified=True):
        return {'trial':trial,'source':'render-dashboard/logs','verified':verified}
    def test_two_confirmed_samples_cannot_create_a_final_config(self):
        result,report,config=self.run_report([self.sample(1),self.sample(2)],[self.proof(1),self.proof(2)])
        self.assertNotEqual(result.returncode,0);self.assertIsNone(report);self.assertIsNone(config)
    def test_three_confirmed_samples_exclude_failed_attempt_and_set_mean_minus_two(self):
        result,report,config=self.run_report([self.sample(1,20),self.sample(2,25),self.sample(3,120,'failed'),self.sample(4,30)],
            [self.proof(1),self.proof(2),self.proof(4)])
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(report['cold']['count'],3)
        self.assertEqual(report['cold']['mean'],25);self.assertEqual(config['storySeconds'],23)
        self.assertEqual(report['excludedAttempts'][0]['trial'],3)
    def test_unverified_log_entry_does_not_confirm_a_start(self):
        result,_,config=self.run_report([self.sample(1),self.sample(2),self.sample(3)],
            [self.proof(1),self.proof(2),self.proof(3,False)])
        self.assertNotEqual(result.returncode,0);self.assertIsNone(config)
    def test_failed_attempt_is_not_counted_even_with_a_shutdown_log(self):
        result,_,_=self.run_report([self.sample(1),self.sample(2),self.sample(3,120,'failed')],
            [self.proof(1),self.proof(2),self.proof(3)])
        self.assertNotEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
