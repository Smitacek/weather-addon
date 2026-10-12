"""Pure DC production model. UTC intervals, local-calendar energy accounting."""
import datetime as dt
import math
import re
import uuid
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc

def timestamp(value):
    t = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return t.astimezone(UTC)

def iso(value):
    return timestamp(value).isoformat().replace('+00:00', 'Z')

def finite(value, name):
    if isinstance(value, bool) or value is None:
        raise ValueError(f'{name} is missing or invalid')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite')
    return number

def normalize_arrays(options):
    arrays = []
    for raw in options.get('pv_arrays', []):
        a = dict(raw)
        if not re.fullmatch(r'[a-z0-9_]{1,32}', str(a.get('id', ''))):
            raise ValueError('PV array id must contain a-z, 0-9 or underscore')
        defaults = dict(gamma_per_c=-0.004, noct_c=45, loss_fraction=0.14,
                        shading_factor=1, geometry_confirmed=False)
        a = {**defaults, **a}
        limits = dict(capacity_kw=(0.001,1000), tilt_deg=(0,90), azimuth_deg=(0,360),
                      gamma_per_c=(-0.02,0), noct_c=(20,100), loss_fraction=(0,0.99),
                      shading_factor=(0,1))
        for key,(low,high) in limits.items():
            a[key] = finite(a.get(key),key)
            if not low <= a[key] <= high:
                raise ValueError(f'{key} outside {low}..{high}')
        if not isinstance(a['geometry_confirmed'],bool):
            raise ValueError('geometry_confirmed must be boolean')
        if any(prev['id']==a['id'] for prev in arrays):
            raise ValueError('Duplicate PV array id')
        arrays.append(a)
    if len(arrays)>8:
        raise ValueError('Maximum 8 PV arrays')
    return arrays

def dc_power_w(poa_w_m2,temp_c,array):
    poa = max(0,finite(poa_w_m2,'POA'))
    air = finite(temp_c,'temperature')
    cell = air+(array['noct_c']-20)*poa/800
    return max(0,array['capacity_kw']*poa*(1+array['gamma_per_c']*(cell-25))
               *(1-array['loss_fraction'])*array['shading_factor'])

def day_bounds(day,tz):
    start = dt.datetime.combine(day,dt.time(),tzinfo=tz).astimezone(UTC)
    end = dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),tzinfo=tz).astimezone(UTC)
    return start,end

def build_profile(hourly,arrays,issued_at,timezone,horizon_h=96,conservative_factor=0.8):
    issued_at=timestamp(issued_at)
    tz=ZoneInfo(timezone)
    end=issued_at+dt.timedelta(hours=horizon_h)
    all_intervals=[]
    previous_end=None
    for h in sorted(hourly,key=lambda h:h['interval_start_utc']):
        start,finish=timestamp(h['interval_start_utc']),timestamp(h['interval_end_utc'])
        duration=(finish-start).total_seconds()/3600
        if not 0<duration<=1 or (previous_end is not None and start<previous_end):
            raise ValueError('Overlapping or invalid forecast intervals')
        previous_end=finish
        modeled={}
        for a in arrays:
            try:
                power=dc_power_w(h.get('poa_w_m2',{}).get(a['id']),h.get('temp_2m_c'),a)
            except (ValueError,TypeError):
                power=None
            modeled[a['id']]={'power_w':power,'energy_kwh':power*duration/1000 if power is not None else None}
        total=sum(r['power_w'] for r in modeled.values()) if modeled and all(r['power_w'] is not None for r in modeled.values()) else None
        all_intervals.append(dict(interval_start_utc=iso(start),interval_end_utc=iso(finish),
            power_w=total,energy_kwh=total*duration/1000 if total is not None else None,
            arrays=modeled,weather={k:v for k,v in h.items() if k not in ('poa_w_m2',)},
            poa_w_m2=h.get('poa_w_m2',{}),quality='valid' if total is not None else 'missing'))
    days=sorted({timestamp(r['interval_start_utc']).astimezone(tz).date() for r in all_intervals
                 if timestamp(r['interval_end_utc'])>issued_at-dt.timedelta(days=1)
                 and timestamp(r['interval_start_utc'])<end})
    daily=[]
    for day in days:
        start,finish=day_bounds(day,tz)
        expected=(finish-start).total_seconds()/3600
        totals={a['id']:0.0 for a in arrays}
        valid_hours=0.0
        remaining_hours=0.0
        remaining_energy=0.0
        for r in all_intervals:
            rs,re=timestamp(r['interval_start_utc']),timestamp(r['interval_end_utc'])
            overlap=max(0,(min(finish,re)-max(start,rs)).total_seconds()/3600)
            remaining=max(0,(min(finish,re)-max(start,rs,issued_at)).total_seconds()/3600)
            if r['power_w'] is not None:
                valid_hours+=overlap
                remaining_hours+=remaining
                remaining_energy+=r['power_w']*remaining/1000
                for aid in totals:
                    totals[aid]+=r['arrays'][aid]['power_w']*overlap/1000
        complete=abs(valid_hours-expected)<1e-6
        remaining_expected=max(0,(finish-max(start,issued_at)).total_seconds()/3600)
        remaining_complete=abs(remaining_hours-remaining_expected)<1e-6
        energy=sum(totals.values()) if complete else None
        daily.append(dict(date_local=day.isoformat(),expected_hours=expected,
            coverage_hours=valid_hours,complete=complete,energy_kwh=energy,
            conservative_energy_kwh=energy*conservative_factor if energy is not None else None,
            remaining_energy_kwh=remaining_energy if remaining_complete else None,
            remaining_complete=remaining_complete,arrays_energy_kwh=totals if complete else None))
    intervals=[]
    for r in all_intervals:
        rs,re=timestamp(r['interval_start_utc']),timestamp(r['interval_end_utc'])
        start,finish=max(rs,issued_at),min(re,end)
        if start>=finish: continue
        fraction=(finish-start).total_seconds()/(re-rs).total_seconds()
        intervals.append({**r,'interval_start_utc':iso(start),'interval_end_utc':iso(finish),
            'partial_interval':fraction<1,'energy_kwh':r['energy_kwh']*fraction if r['energy_kwh'] is not None else None,
            'arrays':{key:{**v,'energy_kwh':v['energy_kwh']*fraction if v['energy_kwh'] is not None else None}
                      for key,v in r['arrays'].items()}})
    return dict(schema_version=2,issue_id=str(uuid.uuid4()),issued_at_utc=iso(issued_at),
        fetched_at_utc=iso(issued_at),model='pvwatts_dc_noct_v1',timezone=timezone,
        array_config=arrays,conservative_factor=conservative_factor,
        assumptions=[f"{a['id']}: geometry unconfirmed" for a in arrays if not a['geometry_confirmed']],
        intervals=intervals,daily=daily)
