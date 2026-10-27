import tempfile
import unittest
from pathlib import Path
from twin.plant import Plant, Settings
from twin.experiments import compare
from twin.storage import ExperimentStore

class AdvancedTests(unittest.TestCase):
    def test_standby_takeover(self):
        p=Plant()
        cfg=Settings(pumps=2,strategy='Standby',pump_trip=True)
        for _ in range(6000): r,_=p.step(cfg)
        self.assertEqual(r['speed_pct'],0)
        self.assertGreater(r['pump2_speed_pct'],0)
        self.assertAlmostEqual(p.level,3,delta=.04)

    def test_parallel_mass_conservation(self):
        p=Plant()
        cfg=Settings(pumps=2,strategy='Assist',demand=.07)
        for _ in range(1500):
            before=p.level
            r,_=p.step(cfg)
            balance=(r['inflow_ls']-r['delivered_ls']-r['leak_ls']-r['overflow_ls'])/1000*.2
            self.assertAlmostEqual((p.level-before)*p.area,balance,places=10)
        self.assertGreater(p.second_speed,0)

    def test_seed_and_filter(self):
        a,b=Plant(),Plant()
        for _ in range(100):
            ra,_=a.step(Settings(noise=.1))
            rb,_=b.step(Settings(noise=.1))
            self.assertEqual(ra,rb)
        rows=a.rows
        raw=sum((r['measured_level_m']-r['level_m'])**2 for r in rows)
        filtered=sum((r['filtered_level_m']-r['level_m'])**2 for r in rows)
        self.assertLess(filtered,raw)

    def test_archive_round_trip(self):
        p=Plant();p.advance(Settings(),1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.db'
            store=ExperimentStore(path)
            identity=store.save("Trial '1'",p)
            new=ExperimentStore(path)
            self.assertEqual(new.load(identity)['rows'],p.rows)
            self.assertEqual(new.list()[0]['name'],"Trial '1'")

    def test_comparison(self):
        result=compare(Settings(),10)
        self.assertEqual(len(result),4)
        self.assertTrue(all(r['Energy (kWh)']>=0 for r in result))

    def test_profiles_and_rotation(self):
        p=Plant();p.time=61
        r,_=p.step(Settings(profile='Step'))
        self.assertAlmostEqual(r['demand_ls'],19.2)
        p.time=301
        p.step(Settings(pumps=2,strategy='Balanced'))
        self.assertEqual(p.lead,1)
