import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject,Signal
from weather import WeatherService,parse_forecast,parse_backup_forecast,parse_openmeteo,save_cached,load_cached,weather_kind,TEHRAN

def samples():
    now=datetime(2026,11,4,8,tzinfo=timezone.utc);local=now.astimezone(TEHRAN);base=local.replace(minute=0,second=0,microsecond=0);weather={'code':1,'fa':'عمدتاً صاف','icon':'🌤️'}
    payload={'location':{'name':'تهران','utc_offset_seconds':12600},'units':{'temperature':'°C'},'current':{'time':local.strftime('%Y-%m-%dT%H:%M'),'temperature':17,'weather':weather},'hourly':[{'time':(base+timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M'),'temperature':10+i/2,'weather':weather} for i in range(24)],'daily':[{'date':(local+timedelta(days=i)).strftime('%Y-%m-%d'),'temp_min':8,'temp_max':17,'weather':weather} for i in range(7)]}
    return now,payload

class WeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_current_and_all_hours_are_native_local_values(self):
        now,payload=samples();result=parse_forecast(payload,now)
        self.assertEqual(len(result['days']),7);self.assertEqual(len(result['hours']),24);self.assertEqual(result['current']['time'].utcoffset(),timedelta(hours=3,minutes=30));self.assertEqual(result['hours'][1]['temp'],10.5);self.assertEqual(weather_kind(payload['current']['weather']),('cloud-sun','عمدتاً صاف'))
    def test_disabled_never_requests(self):
        service=WeatherService()
        with patch('requests.get',side_effect=AssertionError('unexpected network')):service.configure(False);self.assertFalse(service.busy)
        service.timer.stop()
    def test_stale_rejected(self):
        now,payload=samples()
        with self.assertRaises(ValueError):parse_forecast(payload,now+timedelta(days=20))
    def test_observation_time_and_model_fallback_are_distinguished(self):
        from weather_ui import measurement_caption
        now,payload=samples();payload['current']['observation']={'station_name':'ایستگاه نمونه','observed_at':(now-timedelta(minutes=7)).isoformat()};payload['meta']={'current_source':'metar:TEST'}
        result=parse_forecast(payload,now);self.assertEqual(result['current']['observation']['station_name'],'ایستگاه نمونه');self.assertIn('۷ دقیقه',measurement_caption(result,now))
        payload['current']['observation']={'station_name':'ایستگاه نمونه','age_minutes':5};result=parse_forecast(payload,now);self.assertIn('۵ دقیقه',measurement_caption(result,now))
        payload['meta']={'current_source':'open-meteo'};result=parse_forecast(payload,now);self.assertNotIn('observation',result['current']);self.assertEqual(measurement_caption(result,now),'پیش‌بینی مدل')
        payload['meta']={'current_source':'metar:TEST'};payload['current']['observation']['observed_at']='bad';self.assertNotIn('observation',parse_forecast(payload,now)['current'])
    def test_backup_forecast_interpolates_and_labels_estimates(self):
        now=datetime(2026,11,4,8,tzinfo=timezone.utc);base=now.replace(hour=0)
        daily={'dataseries':[{'date':int((now+timedelta(days=i)).strftime('%Y%m%d')),'temp2m':{'min':8,'max':17},'weather':'pcloudy'} for i in range(7)]}
        hourly={'init':base.strftime('%Y%m%d%H'),'dataseries':[{'timepoint':i,'temp2m':i,'weather':'clearday'} for i in range(3,63,3)]}
        result=parse_backup_forecast(daily,hourly,now)
        self.assertTrue(result['estimated']);self.assertEqual(len(result['hours']),24);self.assertEqual(len(result['days']),7);self.assertAlmostEqual(result['hours'][0]['temp'],8.5)
    def test_openmeteo_model_never_claims_station_observation(self):
        from weather_ui import measurement_caption
        now,payload=samples();current=payload['current'];hours=payload['hourly'];days=payload['daily']
        model={'utc_offset_seconds':12600,'current':{'time':current['time'],'temperature_2m':17,'weather_code':1,'is_day':1},'hourly':{'time':[x['time'] for x in hours],'temperature_2m':[x['temperature'] for x in hours],'weather_code':[1]*24},'daily':{'time':[x['date'] for x in days],'temperature_2m_min':[8]*7,'temperature_2m_max':[17]*7,'weather_code':[1]*7}}
        result=parse_openmeteo(model,now)
        self.assertEqual(len(result['hours']),24);self.assertEqual(len(result['days']),7)
        self.assertNotIn('observation',result['current']);self.assertEqual(measurement_caption(result,now),'پیش‌بینی مدل')
        with self.assertRaises(ValueError):parse_openmeteo(model,now+timedelta(days=1))
        model['current']['temperature_2m']=1000
        with self.assertRaises(ValueError):parse_openmeteo(model,now)
    def test_unavailable_primary_uses_model_and_preserves_data_on_failure(self):
        import requests
        now,payload=samples();forecast=parse_forecast(payload,now)
        class InlineThread:
            def __init__(self,target,daemon):self.target=target
            def start(self):self.target()
        service=WeatherService();service.timer.stop();service.enabled=True;service.base_url='https://example.test'
        with patch('weather.threading.Thread',InlineThread),patch('weather.requests.get',side_effect=requests.ConnectionError()),patch('weather.fetch_openmeteo',return_value=forecast),patch('weather.save_cached'):
            service.refresh();self.assertIs(service.data,forecast);self.assertFalse(service.busy);self.assertFalse(service.error)
        service.next_check=0
        with patch('weather.threading.Thread',InlineThread),patch('weather.requests.get',side_effect=requests.ConnectionError()),patch('weather.fetch_openmeteo',side_effect=requests.ConnectionError()):
            service.refresh();self.assertIs(service.data,forecast);self.assertTrue(service.error);self.assertLessEqual(service.next_check-__import__('time').time(),60)
    def test_cache_roundtrip_and_timestamp(self):
        import tempfile
        from pathlib import Path
        now,payload=samples();data=parse_forecast(payload,now)
        with tempfile.TemporaryDirectory() as directory,patch('weather.app_dir',return_value=Path(directory)):
            stamp=datetime.now(TEHRAN);save_cached(data,stamp);result,checked=load_cached()
            self.assertEqual(result['hours'][0]['time'],data['hours'][0]['time']);self.assertEqual(result['days'][0]['date'],data['days'][0]['date']);self.assertEqual(checked,stamp)
            save_cached(data,stamp-timedelta(days=3));self.assertEqual(load_cached(),(None,None))
    def test_previous_endpoint_migrates_but_custom_endpoint_is_retained(self):
        import tempfile,os
        import storage
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'TAXCALENDAR_DATA_DIR':directory}):
            storage.set_profile(None);data=storage.load_data();data['settings']['weather_api_base']='https://f1a494a8c367d2.lhr.life/';storage.save_data(data)
            self.assertEqual(storage.load_data()['settings']['weather_api_base'],'')
            data=storage.load_data();data['settings']['weather_api_base']='https://example.com';storage.save_data(data)
            self.assertEqual(storage.load_data()['settings']['weather_api_base'],'https://example.com')
    def test_ui_displays_separate_sections(self):
        from types import SimpleNamespace
        from copy import deepcopy
        from storage import DEFAULT_SETTINGS
        from weather_ui import WeatherWidget
        from PySide6.QtWidgets import QDialog,QFrame,QScrollArea
        class FakeService(QObject):changed=Signal()
        now,payload=samples();service=FakeService();service.data=parse_forecast(payload,now);service.busy=False;service.error='';service.checked_at=now;owner=SimpleNamespace(data={'settings':deepcopy(DEFAULT_SETTINGS)})
        widget=WeatherWidget(owner,service);widget.resize(900,150);widget.show();self.app.processEvents();self.assertEqual(widget.content.count(),7);self.assertTrue(widget.details.isVisible())
        with patch.object(QDialog,'exec',autospec=True) as opened:
            widget.show_details();self.assertTrue(opened.called);dialog=widget.findChild(QDialog);self.assertEqual(len(dialog.findChildren(QFrame,'ForecastGlass')),3);self.assertEqual(dialog.findChild(QScrollArea).widget().layout().count(),25)
        self.assertEqual(widget.hour_row.count(),24);self.assertEqual(widget.content.count(),7)
        owner.data['settings'].update(weather_hourly=False,weather_weekly=False);widget.render();self.assertTrue(widget.hour_host.isHidden());self.assertTrue(widget.week_host.isHidden())
        widget.close()
    def test_comparison_button_fetches_and_displays_numeric_difference(self):
        from types import SimpleNamespace
        from copy import deepcopy
        from PySide6.QtCore import QEventLoop,QTimer
        from PySide6.QtWidgets import QDialog,QPushButton,QLabel
        from storage import DEFAULT_SETTINGS
        from weather_ui import WeatherWidget
        now,payload=samples();service=WeatherService();service.data=parse_forecast(payload,now);service.checked_at=now;owner=SimpleNamespace(data={'settings':deepcopy(DEFAULT_SETTINGS)})
        widget=WeatherWidget(owner,service);widget.show();self.app.processEvents()
        class Response:
            is_redirect=False;content=b'{}'
            def raise_for_status(self):pass
            def json(self):return {'model':{'temperature':15.7},'observation':{'temperature':13}}
        def open_dialog(dialog):
            button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='مقایسه با مدل')
            loop=QEventLoop();service.comparison_done.connect(lambda *_:QTimer.singleShot(10,loop.quit));QTimer.singleShot(3000,loop.quit);button.click();loop.exec()
            text=' '.join(label.text() for label in dialog.findChildren(QLabel))
            self.assertIn('۲.۷',text);self.assertIn('ایستگاه',text);return 0
        with patch('requests.get',return_value=Response()),patch.object(QDialog,'exec',open_dialog):widget.show_details()
        widget.close();service.timer.stop()

if __name__=='__main__':unittest.main()
