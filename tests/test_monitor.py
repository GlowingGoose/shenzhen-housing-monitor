import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile
import pandas as pd
from housing_monitor import build_signal, _parse_overall_table, parse_release
import refresh

ROOT=Path(__file__).resolve().parents[1]

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.data=pd.read_csv(ROOT/'data/official_70city_prices.csv')

    def test_gap_does_not_count_as_consecutive(self):
        months=sorted(self.data['月份'].unique())
        sample=self.data[~self.data['月份'].eq(months[-2])]
        result=build_signal(sample)
        self.assertIsNone(result['深圳二手近3期累计_pct'])
        self.assertIsNone(result['深圳二手近6期累计_pct'])
        self.assertLessEqual(result['深圳二手连续上涨月数'],1)

    def test_six_month_product(self):
        result=build_signal(self.data)
        sz=self.data[(self.data['城市']=='深圳')&(self.data['市场']=='二手')].sort_values('月份').tail(6)
        expected=round((sz['环比指数'].prod()/100**6-1)*100,2)
        self.assertAlmostEqual(result['深圳二手近6期累计_pct'],expected)

    def test_january_six_columns_and_city_whitespace(self):
        table=pd.DataFrame([['城市','环比','同比','城市','环比','同比'],['上月','100','100','上月','100','100'],['深　圳',100.3,95.2,'哈 尔 滨',99.1,94]])
        result=_parse_overall_table(table,'2026-01','二手','https://www.stats.gov.cn/')
        self.assertEqual([r['城市'] for r in result],['深圳','哈尔滨'])

    def test_wrong_month_rejected(self):
        html='<html><title>2026年8月份70个大中城市商品住宅销售价格变动情况</title></html>'
        with patch('housing_monitor.get_html',return_value=html):
            with self.assertRaises(ValueError):
                parse_release('2026-07','https://www.stats.gov.cn/release')

    def test_failure_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'data').mkdir()
            (root/'data/official_70city_prices.csv').write_text('sentinel')
            with patch.object(refresh,'ROOT',root),patch.object(refresh,'discover_latest_release',side_effect=RuntimeError('network unavailable')):
                self.assertEqual(refresh.refresh(),1)
            self.assertEqual((root/'data/official_70city_prices.csv').read_text(),'sentinel')
            self.assertIn('network unavailable',(root/'data/status.json').read_text())

if __name__=='__main__':
    unittest.main()
