#!/usr/bin/env python3
import datetime as dt
import json
import logging
from pathlib import Path
from fastapi import FastAPI,HTTPException
from zoneinfo import ZoneInfo
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
    @app.get('/api/comparison')
    async def comparison(period: str='day',date: str|None=None):
        report=store.snapshot()['solar_comparison']
        timezone=report.get('timezone','Europe/Prague');tz=ZoneInfo(timezone)
        now=dt.datetime.now(dt.timezone.utc);today=now.astimezone(tz).date()
        try:
            selected=dt.date.fromisoformat(date) if date else today
            if period=='day': start=selected;end=start+dt.timedelta(days=1)
            elif period=='week': start=selected-dt.timedelta(days=selected.weekday());end=start+dt.timedelta(days=7)
            elif period=='month':
                start=selected.replace(day=1);end=(start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1))
            else: raise ValueError('period')
        except (ValueError,TypeError): raise HTTPException(400,'Choose day/week/month and an ISO date')
        days=[];cursor=start
        source={r['date_local']:r for r in report.get('days',[])}
        while cursor<min(end,today+dt.timedelta(days=1)):
            row=source.get(cursor.isoformat())
            if row: days.append(row)
            else:
                day_start=dt.datetime.combine(cursor,dt.time(),tz).astimezone(dt.timezone.utc)
                day_end=dt.datetime.combine(cursor+dt.timedelta(days=1),dt.time(),tz).astimezone(dt.timezone.utc)
                duration=(day_end-day_start).total_seconds()/3600
                elapsed=max(0,(min(day_end,now)-day_start).total_seconds()/3600)
                days.append(dict(date_local=cursor.isoformat(),actual_energy_kwh=None,predicted_energy_kwh=None,
                comparable=False,coverage_fraction=0,eligible_fraction=0,curtailed_fraction=0,
                expected_hours=duration,elapsed_hours=elapsed,partial=now<day_end,hours=[]))
            cursor+=dt.timedelta(days=1)
        paired=[r for r in days if r.get('comparable')]
        def total(rows,key):
            values=[r[key] for r in rows if r.get(key) is not None]
            return sum(values) if values else None
        predicted=total(paired,'predicted_energy_kwh');actual=total(paired,'actual_energy_kwh')
        error=actual-predicted if paired else None
        hours=sum(r['elapsed_hours'] for r in days)
        summary=dict(actual_energy_kwh=total(days,'actual_energy_kwh'),predicted_energy_kwh=total(days,'predicted_energy_kwh'),
            matched_actual_energy_kwh=actual,matched_predicted_energy_kwh=predicted,error_kwh=error,
            error_pct=error/predicted*100 if error is not None and predicted>0 else None,
            mae_kwh=sum(abs(r['error_kwh']) for r in paired)/len(paired) if paired else None,
            comparable_days=len(paired),expected_days=len(days),days_with_measurements=sum(r.get('actual_energy_kwh') is not None for r in days),
            coverage_fraction=sum(r['coverage_fraction']*r['elapsed_hours'] for r in days)/hours if hours else None,
            curtailed_fraction=sum(r['curtailed_fraction']*r['elapsed_hours'] for r in days)/hours if hours else None,
            eligible_fraction=sum(r['eligible_fraction']*r['elapsed_hours'] for r in days)/hours if hours else None)
        try: fresh=0<=(now-parse_time(report['updated_at_utc'])).total_seconds()<=900
        except (KeyError,TypeError,ValueError): fresh=False
        return JSONResponse(dict(period=period,selected_date=selected.isoformat(),start_date=start.isoformat(),end_date=end.isoformat(),
            timezone=timezone,baseline_local_time='22:00',fresh=fresh,updated_at_utc=report.get('updated_at_utc'),
            first_observation_utc=report.get('first_observation_utc'),summary=summary,days=days))
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
