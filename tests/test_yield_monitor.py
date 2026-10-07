import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import build_site
import yield_monitor

ROOT = Path(__file__).resolve().parents[1]


class YieldMonitorTests(unittest.TestCase):
    def test_parse_and_match_same_city_month(self):
        matched = pd.read_csv(ROOT / 'data/rent_sale_yield.csv')['城市'].tolist()
        names = matched + [f'非统计局城市{i}' for i in range(8)]
        def page(cities, month, unit, value):
            rows = [{'city': city, 'cityId': i + 1, 'date': month,
                     'averageUnit': unit, 'average': value}
                    for i, city in enumerate(cities)]
            state = {'data': {'cityIndexInfo': rows}}
            return '<script>window.__INITIAL_STATE__=' + json.dumps(state, ensure_ascii=False) + ';</script>'

        rent_month, rents = yield_monitor.parse_city_prices(
            page(names, '2026年9月', '元/平方米/月', 100), 'rent')
        sale_month, sales = yield_monitor.parse_city_prices(
            page(names + [f'其他城市{i}' for i in range(50)],
                 '2026年9月', '元/平方米', 60000), 'sale')
        result = yield_monitor.combine(rent_month, rents, sale_month, sales)
        self.assertEqual(len(result), 42)
        self.assertEqual(set(result['城市']), set(matched))
        self.assertTrue(result['毛租金回报率_pct'].eq(2).all())
        with self.assertRaisesRegex(ValueError, '不在同月'):
            yield_monitor.combine(rent_month, rents, '2026-08', sales)
        sales['深圳']['id'] = -1
        with self.assertRaisesRegex(ValueError, '城市 ID'):
            yield_monitor.combine(rent_month, rents, sale_month, sales)

    def test_failure_preserves_last_yield_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data').mkdir()
            snapshot = root / 'data/rent_sale_yield.csv'
            snapshot.write_text('sentinel', encoding='utf-8')
            with patch.object(yield_monitor, 'ROOT', root), patch.object(
                yield_monitor, 'fetch_html', side_effect=RuntimeError('source changed')
            ):
                self.assertEqual(yield_monitor.refresh(), 1)
            self.assertEqual(snapshot.read_text(encoding='utf-8'), 'sentinel')
            status = json.loads((root / 'data/yield_status.json').read_text())
            self.assertFalse(status['ok'])
            self.assertIn('source changed', status['message'])

    def test_dashboard_exposes_only_matched_cities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / 'site', root / 'site')
            (root / 'data').mkdir()
            for file in ('official_70city_prices.csv', 'rent_sale_yield.csv',
                         'status.json', 'yield_status.json'):
                shutil.copy(ROOT / 'data' / file, root / 'data' / file)
            with patch.object(build_site, 'ROOT', root):
                build_site.build()
            payload = json.loads((root / 'dist/dashboard.json').read_text())
            price_cities = {r[1] for r in payload['records']}
            yield_cities = {r[1] for r in payload['yields']}
            self.assertEqual(len(price_cities), 42)
            self.assertEqual(price_cities, yield_cities)
            self.assertIn('重庆', price_cities)
            self.assertNotIn('唐山', price_cities)
            self.assertEqual(set(pd.read_csv(root / 'dist/matched-city-prices.csv')['城市']), price_cities)


if __name__ == '__main__':
    unittest.main()
