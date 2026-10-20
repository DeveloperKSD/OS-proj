import pytest
from alerts import DEFAULT_THRESHOLDS, LeakDetector, evaluate_alerts
from collector import detect_environment, safe_rate
from stress import StressManager

def sample(**kwargs):
    s={'cpu':20,'mem':40,'swap':0,'ctx':10,'rd':0,'wr':0,'volumes':{'/':{'percent':50}}}; s.update(kwargs); return s

def test_counter_rate_and_reset():
    assert safe_rate(150,100,5)==10
    assert safe_rate(2,100,5)==0
    assert safe_rate(None,100,5)==0
    assert safe_rate(10,0,0)==0

def test_environment_is_known_value():
    assert detect_environment() in ('docker-container','native-host')

def test_cpu_threshold_requires_duration():
    t=dict(DEFAULT_THRESHOLDS)
    assert not any(a['id']=='cpu_saturation' for a in evaluate_alerts(sample(cpu=95),t,5,0,[],100))
    alerts=evaluate_alerts(sample(cpu=95),t,10,0,[],100)
    assert any(a['id']=='cpu_saturation' and '95.0%' in a['message'] for a in alerts)

def test_leak_detector_uses_seconds_and_growth():
    d=LeakDetector(window_seconds=20,growth_mb=10); key=(42,1.0)
    assert not d.update(0,{key:1_000_000})
    assert not d.update(10,{key:8_000_000})
    found=d.update(20,{key:15_000_000})
    assert found and found[0]['pid']==42 and found[0]['growth_mb']>10

def test_stress_caps_and_one_at_a_time():
    m=StressManager(enabled=True)
    with pytest.raises(ValueError): m.start('cpu',{'duration':121})
    with pytest.raises(ValueError): m.start('memory',{'size_mb':2049})
    with pytest.raises(ValueError): m.start('disk',{'duration':10,'size_mb':1025})
    first=m.start('cpu',{'duration':2})
    assert first['active'] and first['kind']=='cpu'
    with pytest.raises(RuntimeError): m.start('disk',{'duration':2,'size_mb':8})
    m.stop()

def test_disabled_stress():
    with pytest.raises(ValueError): StressManager(False).start('cpu',{'duration':1})

def test_api_response_shape():
    pytest.importorskip('flask')
    import app as server
    client=server.app.test_client()
    assert client.get('/api/status').status_code==200
    assert 'ready' in client.get('/api/status').get_json()
    assert client.get('/api/history').status_code==200
    config=client.get('/api/config').get_json()
    assert 'thresholds' in config and 'sample_interval' in config
    assert client.get('/healthz').get_json()['status']=='ok'
