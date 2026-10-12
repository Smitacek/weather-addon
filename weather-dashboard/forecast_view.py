"""Current forecast power and energy clipped to the remaining local day."""
import datetime as dt
from zoneinfo import ZoneInfo
from mqtt_listener import parse_time

def remaining_today(profile,now):
    tz=ZoneInfo(profile.get('timezone','Europe/Prague'));local=now.astimezone(tz)
    finish=dt.datetime.combine(local.date()+dt.timedelta(days=1),dt.time(),tz).astimezone(dt.timezone.utc)
    intervals=[];energy=0;covered=0
    for r in profile.get('intervals',[]):
        start=max(now,parse_time(r['interval_start_utc']));end=min(finish,parse_time(r['interval_end_utc']))
        if end<=start:continue
        row={**r,'interval_start_utc':start.isoformat().replace('+00:00','Z'),'interval_end_utc':end.isoformat().replace('+00:00','Z')}
        intervals.append(row)
        if r['power_w'] is not None:
            seconds=(end-start).total_seconds();energy+=r['power_w']*seconds/3600000;covered+=seconds
    known=[r for r in intervals if r['power_w'] is not None]
    peak=max(known,key=lambda r:r['power_w']) if known else None
    return dict(intervals=intervals,energy_kwh=energy if abs(covered-(finish-now).total_seconds())<0.01 else None,
        peak_power_w=peak['power_w'] if peak else None,peak_at_utc=peak['interval_start_utc'] if peak else None,end_utc=finish.isoformat().replace('+00:00','Z'))
