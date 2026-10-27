import unittest
from twin.plant import Plant, Settings

class PlantTests(unittest.TestCase):
    def test_control_converges(self):
        p=Plant()
        for _ in range(6000): p.step(Settings())
        self.assertAlmostEqual(p.level, 3, delta=.03)

    def test_mass_balance(self):
        p=Plant()
        for _ in range(1500):
            before=p.level
            r,_=p.step(Settings(mode='Manual',manual_speed=1,leak=.005))
            change=(r['inflow_ls']-r['delivered_ls']-r['leak_ls']-r['overflow_ls'])/1000*.2
            self.assertAlmostEqual((p.level-before)*p.area,change,places=10)
            self.assertTrue(0 <= p.level <= 5)

    def test_blockage_reduces_flow(self):
        p,q=Plant(),Plant()
        for _ in range(50):
            normal,_=p.step(Settings(mode='Manual',manual_speed=.8))
            blocked,alerts=q.step(Settings(mode='Manual',manual_speed=.8,blockage=.8))
        self.assertLess(blocked['inflow_ls'],normal['inflow_ls']*.4)
        self.assertIn('Flow restriction suspected',alerts)

    def test_shutdown_and_empty_tank(self):
        p=Plant()
        for _ in range(5000): r,_=p.step(Settings(pump_enabled=False))
        self.assertEqual(p.level,0)
        self.assertEqual(r['power_kw'],0)
        self.assertEqual(r['delivered_ls'],0)

    def test_sensor_fault(self):
        _,alerts=Plant().step(Settings(sensor_bias=.8))
        self.assertIn('Level sensor disagreement',alerts)

    def test_time_step_validation(self):
        with self.assertRaises(ValueError): Plant().step(Settings(),0)

if __name__=='__main__': unittest.main()
