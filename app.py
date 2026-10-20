"""OS Observatory Flask entry point. All measurements come from psutil."""
from __future__ import annotations
import atexit, collections, logging, os, platform, threading, time
from typing import Any
import psutil
from flask import Flask, jsonify, request
from prometheus_client import Gauge, start_http_server
from alerts import DEFAULT_THRESHOLDS, LeakDetector, evaluate_alerts
from collector import collect_base, detect_environment, process_snapshot, safe_rate
from stress import StressManager

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'), format='%(asctime)s %(levelname)s %(message)s')
log=logging.getLogger('os-observatory')
UI_PORT=int(os.getenv('UI_PORT','5050')); METRICS_PORT=int(os.getenv('METRICS_PORT','8000')); INTERVAL=max(1.0,float(os.getenv('SAMPLE_INTERVAL','5')))
ENABLE_METRICS=os.getenv('ENABLE_METRICS','1')!='0'; ENABLE_STRESS=os.getenv('ENABLE_STRESS','1')!='0'
_env=detect_environment(); SHOW_NAMES=os.getenv('SHOW_PROCESS_NAMES', '0' if _env=='docker-container' else '1')=='1'
THRESHOLDS={k:float(os.getenv('ALERT_'+k.upper(),str(v))) for k,v in DEFAULT_THRESHOLDS.items()}
app=Flask(__name__, static_folder='static', static_url_path='/static')
stress=StressManager(ENABLE_STRESS); STATE:dict[str,Any]={'ready':False}; history=collections.deque(maxlen=max(2,int(600/INTERVAL))); event_log=collections.deque(maxlen=20)
prev:dict[str,Any]={}; hot_cpu=hot_disk=0.0; last_alerts:set[str]=set(); active_since:dict[str,float]={}; leak_detector=LeakDetector(THRESHOLDS['leak_window_seconds'],THRESHOLDS['leak_growth_mb'])

def gauge(name:str, desc:str, labels:list[str]|None=None): return Gauge(name,desc,labels or [])
G={k:gauge(n,d) for k,n,d in [
 ('cpu','os_cpu_percent','CPU utilisation percent'),('mem','os_mem_percent','Memory used percent'),('swap','os_swap_percent','Swap used percent'),('rd','os_disk_read_bytes_per_s','Disk read bytes per second'),('wr','os_disk_write_bytes_per_s','Disk write bytes per second'),('ctx','os_ctx_switches_per_s','Context switches per second'),('intr','os_interrupts_per_s','Interrupts per second'),('procs','os_process_count','Process count'),('threads','os_thread_count','Thread count'),('health','os_health_score','Heuristic health score 0-100'),('netup','os_network_upload_bytes_per_s','Network upload bytes per second'),('netdown','os_network_download_bytes_per_s','Network download bytes per second'),('uptime','os_uptime_seconds','System uptime seconds'),('memused','os_mem_used_bytes','Memory used bytes'),('memtotal','os_mem_total_bytes','Memory total bytes'),('load1','os_load_average_1m','One minute load average') ]}
G_MODE=gauge('os_cpu_mode_percent','CPU time by supported mode',['mode']); G_CORE=gauge('os_cpu_core_percent','Per-core CPU utilisation',['core']); G_ALERT=gauge('os_alert_active','1 when alert active',['alert']); G_VOL=gauge('os_disk_used_percent','Volume usage percent',['volume'])

def sampler() -> None:
    global prev,hot_cpu,hot_disk,last_alerts,active_since
    psutil.cpu_percent(None); psutil.cpu_percent(None,percpu=True); psutil.cpu_times_percent(None)
    previous_time=time.time(); previous=collect_base(); previous_processes={}
    while True:
      time.sleep(INTERVAL)
      try:
        now=time.time(); dt=max(.001,now-previous_time); cur=collect_base()
        rd=safe_rate(cur['io_read'],previous.get('io_read'),dt); wr=safe_rate(cur['io_write'],previous.get('io_write'),dt)
        ctx=safe_rate(cur['ctx_total'],previous.get('ctx_total'),dt); intr=safe_rate(cur['intr_total'],previous.get('intr_total'),dt)
        netup=safe_rate(cur['net_sent'],previous.get('net_sent'),dt); netdown=safe_rate(cur['net_recv'],previous.get('net_recv'),dt)
        nprocs,nthreads,topcpu,topmem,rss=process_snapshot(SHOW_NAMES)
        leaks=leak_detector.update(now,rss)
        cpu_hot=cur['cpu']>=THRESHOLDS['cpu_percent']; disk_hot=rd+wr>=THRESHOLDS['disk_bytes_per_s']
        hot_cpu=hot_cpu+dt if cpu_hot else 0; hot_disk=hot_disk+dt if disk_hot else 0
        sample={'cpu':cur['cpu'],'mem':cur['mem'],'swap':cur['swap'],'ctx':ctx,'rd':rd,'wr':wr,'volumes':cur['volumes']}
        alerts=evaluate_alerts(sample,THRESHOLDS,hot_cpu,hot_disk,leaks,now)
        active_ids={a['id'] for a in alerts}
        for a in alerts:
          if a['id'] not in last_alerts: event_log.appendleft({'time':now,'event':'started',**a})
          active_since.setdefault(a['id'], now)
          a['started_at']=active_since[a['id']]
        for ident in last_alerts-active_ids:
          event_log.appendleft({'time':now,'event':'cleared','id':ident,'level':'info','message':f'{ident.replace("_"," ")} cleared'})
          active_since.pop(ident,None)
        last_alerts=active_ids
        score=max(0,min(100,100-max(0,cur['cpu']-80)*.3-max(0,cur['mem']-80)*.5-sum(20 if a['level']=='bad' else 10 for a in alerts)))
        # Only platform-supported CPU modes are returned.
        modes=cur['modes']; supported={k:v for k,v in modes.items() if k in ('user','system','idle','nice','iowait','irq','softirq','steal','guest','guest_nice','interrupt','dpc')}
        state={'ready':True,'ts':now,'sample_interval':INTERVAL,'environment':_env,'os_name':platform.system(),'os_release':platform.release(),'cpu_cores':psutil.cpu_count(logical=True) or 1,'ram_total_gb':cur['mem_total_gb'],'show_process_names':SHOW_NAMES,
          'cpu':cur['cpu'],'per_core':cur['per_core'],'modes':supported,'mem':cur['mem'],'mem_used_gb':cur['mem_used_gb'],'mem_total_gb':cur['mem_total_gb'],'swap':cur['swap'],'swap_used_gb':cur['swap_used_gb'],'swap_total_gb':cur['swap_total_gb'],
          'health':score,'rd':rd,'wr':wr,'net_up':netup,'net_down':netdown,'ctx':ctx,'intr':intr,'procs':nprocs,'threads':nthreads,'uptime_seconds':cur['uptime_seconds'],'load_average':cur['load_average'],'volumes':cur['volumes'],'top_cpu':topcpu,'top_memory':topmem,'alerts':alerts,'alert_events':list(event_log),'thresholds':THRESHOLDS,'stress':stress.status()}
        STATE.clear(); STATE.update(state)
        history.append({'ts':now,'cpu':cur['cpu'],'mem':cur['mem'],'rd':rd,'wr':wr,'net_up':netup,'net_down':netdown})
        for key in ('cpu','mem','swap','rd','wr','ctx','intr','procs','threads','health','netup','netdown','uptime'): G[key].set({'cpu':cur['cpu'],'mem':cur['mem'],'swap':cur['swap'],'rd':rd,'wr':wr,'ctx':ctx,'intr':intr,'procs':nprocs,'threads':nthreads,'health':score,'netup':netup,'netdown':netdown,'uptime':cur['uptime_seconds']}[key])
        G['memused'].set(cur['mem_used_gb']*1e9); G['memtotal'].set(cur['mem_total_gb']*1e9)
        if cur['load_average']: G['load1'].set(cur['load_average'][0])
        for k,v in supported.items(): G_MODE.labels(k).set(v)
        for i,v in enumerate(cur['per_core']): G_CORE.labels(str(i)).set(v)
        for a in DEFAULT_THRESHOLDS: pass
        for ident in ['cpu_saturation','memory_pressure','thrashing','memory_leak','high_context_switches','heavy_disk_io','low_disk_space']: G_ALERT.labels(ident).set(1 if ident in active_ids else 0)
        for k,v in cur['volumes'].items(): G_VOL.labels(k).set(v['percent'])
        previous,previous_time=cur,now
      except Exception:
        log.exception('Sampler iteration failed; will retry on next interval')

@app.get('/')
def index(): return app.send_static_file('index.html')
@app.get('/healthz')
def healthz(): return jsonify(status='ok',ready=bool(STATE.get('ready'))),200
@app.get('/api/status')
def status(): return jsonify(STATE)
@app.get('/api/history')
def api_history(): return jsonify(list(history))
@app.get('/api/config')
def config(): return jsonify({'sample_interval':INTERVAL,'ui_port':UI_PORT,'metrics_port':METRICS_PORT,'metrics_enabled':ENABLE_METRICS,'stress_enabled':ENABLE_STRESS,'show_process_names':SHOW_NAMES,'thresholds':THRESHOLDS})
@app.get('/api/stress/status')
def stress_status(): return jsonify(stress.status())
@app.post('/api/stress/<kind>')
def stress_start(kind:str):
    if request.remote_addr not in ('127.0.0.1','::1') and not _env=='docker-container': return jsonify(error='Stress tests are available only to local clients.'),403
    try: return jsonify(stress.start(kind,request.get_json(silent=True) or {})),202
    except ValueError as e: return jsonify(error=str(e)),400
    except RuntimeError as e: return jsonify(error=str(e)),409
@app.post('/api/stress/stop')
def stress_stop(): return jsonify(stress.stop())

@atexit.register
def shutdown_stress():
    try: stress.stop()
    except Exception: log.exception('Could not stop stress subprocess cleanly')

if __name__=='__main__':
    if ENABLE_METRICS:
      try: start_http_server(METRICS_PORT, addr='0.0.0.0' if _env=='docker-container' else '127.0.0.1')
      except OSError: log.exception('Could not start Prometheus exporter on port %s',METRICS_PORT)
    threading.Thread(target=sampler,name='metric-sampler',daemon=True).start()
    host=os.getenv('UI_HOST','127.0.0.1')
    # Container deployments override this explicitly in compose.
    if _env=='docker-container': host='0.0.0.0'
    log.info('OS Observatory UI http://%s:%s | environment=%s | metrics=%s',host,UI_PORT,_env,ENABLE_METRICS)
    app.run(host=host,port=UI_PORT,threaded=True)
