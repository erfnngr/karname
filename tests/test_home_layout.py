import unittest
from home_layout import initial_widgets,pack_widgets

class HomeLayoutTests(unittest.TestCase):
    def test_layout_packing_has_no_overlaps_even_with_tall_wide_cards(self):
        placement=pack_widgets(['a','b','c','d'],{'a':2,'b':1,'c':2},{'a':2,'c':2},3);occupied=set()
        for _,row,col,height,width in placement:
            self.assertLessEqual(col+width,3)
            cells={(r,c) for r in range(row,row+height) for c in range(col,col+width)}
            self.assertTrue(occupied.isdisjoint(cells));occupied.update(cells)
        self.assertEqual([x[0] for x in placement],['a','b','c','d'])
    def test_default_widgets_respect_weather_and_quote(self):
        self.assertEqual(initial_widgets('default',False,False),['today','attendance'])
        self.assertIn('weather',initial_widgets('glass_mist',True,True))
        self.assertIn('quote',initial_widgets('glass_mist',True,True))
