#!/usr/bin/env python3
import datetime as dt
import json
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from mqtt_listener import DataStore,MQTTIngest,parse_time

WEB_DIR=Path(__file__).with_name('web')

def create_app(store):
    app=FastAPI()
    app.mount('/static',StaticFiles(directory=WEB_DIR),name='static')
    @app.get('/',response_class=HTMLResponse)
    async def index(): return HTMLResponse(WEB_DIR.joinpath('index.html').read_text())
    @app.get('/api/now')
    async def now(): return JSONResponse({'now':store.snapshot()['now']})
    @app.get('/api/daily')
    async def daily():
        snap=store.snapshot()
        return JSONResponse({'series':snap['daily_series'],'today':snap['daily_today'],'tomorrow':snap['daily_tomorrow']})
    @app.get('/api/solar')
    async def solar():
        snap=store.snapshot();valid=False;age=None
        try:
            age=(dt.datetime.now(dt.timezone.utc)-parse_time(snap['solar']['issued_at_utc'])).total_seconds()
            reported=(dt.datetime.now(dt.timezone.utc)-parse_time(snap['solar_health']['ts_utc'])).total_seconds()
            valid=(snap['solar_health'].get('forecast_valid') is True and 0<=age<=snap['solar_health'].get('ttl_s',900) and 0<=reported<=90)
        except (KeyError,TypeError,ValueError): pass
        observed=snap['solar_observed']
        try: observed_fresh=0<=(dt.datetime.now(dt.timezone.utc)-parse_time(observed['ts_utc'])).total_seconds()<=90
        except (KeyError,ValueError,TypeError): observed_fresh=False
        return JSONResponse(dict(profile=snap['solar'],health=snap['solar_health'],evaluation=snap['solar_evaluation'],
            observed=observed,observed_series=snap['solar_observed_series'],observed_fresh=observed_fresh,valid=valid,age_s=age))
    return app

def main():
    options=json.loads(Path('/data/options.json').read_text())
    logging.basicConfig(level=getattr(logging,str(options.get('log_level','info')).upper(),logging.INFO))
    store=DataStore()
    MQTTIngest(options.get('mqtt_host','core-mosquitto'),int(options.get('mqtt_port',1883)),
        options.get('mqtt_username',''),options.get('mqtt_password',''),options.get('topic_prefix','weather'),
        options.get('site_id','default'),store).start()
    uvicorn.run(create_app(store),host='0.0.0.0',port=8099)

if __name__=='__main__': main()
