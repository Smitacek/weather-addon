"""Open-Meteo forecast normalized to SI; radiation is a preceding-hour mean."""
import datetime as dt
import requests
from solar_model import timestamp, iso, finite

OPEN_METEO_URL='https://api.open-meteo.com/v1/forecast'
FIELDS={'temperature_2m':'temp_2m_c','relative_humidity_2m':'relative_humidity_pct',
 'dew_point_2m':'dew_point_c','pressure_msl':'mslp_hpa','precipitation':'precip_mm',
 'precipitation_probability':'precip_probability_pct','cloud_cover':'cloud_cover_pct',
 'shortwave_radiation':'ghi_w_m2','direct_normal_irradiance':'dni_w_m2',
 'diffuse_radiation':'dhi_w_m2','wind_speed_10m':'wind_speed_10m_ms',
 'wind_direction_10m':'wind_dir_10m_deg','wind_gusts_10m':'wind_gust_10m_ms','visibility':'visibility_m'}

def provider_azimuth(north_deg):
    return (north_deg-180+180)%360-180

def times(data):
    h=data.get('hourly',{})
    stamps=h.get('time',[])
    if not isinstance(stamps,list) or not stamps:
        raise ValueError('No hourly forecast')
    for key,values in h.items():
        if not isinstance(values,list) or len(values)!=len(stamps):
            raise ValueError(f'Invalid hourly field length: {key}')
    return [timestamp(t if t.endswith('Z') or '+' in t else t+'Z') for t in stamps]

def parse_hourly(data):
    stamps=times(data)
    h=data['hourly']
    out=[]
    for i,end in enumerate(stamps):
        rec={'ts_utc':iso(end),'interval_start_utc':iso(end-dt.timedelta(hours=1)),
             'interval_end_utc':iso(end),'poa_w_m2':{}}
        for source,target in FIELDS.items():
            raw=h.get(source,[None]*len(stamps))[i]
            rec[target]=None if raw is None else finite(raw,source)
        out.append(rec)
    return out

def merge_poa(rows,data,array_id):
    stamps=times(data)
    values=data['hourly'].get('global_tilted_irradiance')
    if values is None: raise ValueError('Missing tilted irradiance')
    by_time={iso(t):None if v is None else finite(v,'GTI') for t,v in zip(stamps,values)}
    for row in rows:
        row['poa_w_m2'][array_id]=by_time.get(row['interval_end_utc'])

def fetch_open_meteo(*,latitude,longitude,hourly_horizon_h,forecast_days,units='metric',
                     arrays=None,provider_model='auto',timezone='UTC'):
    if units!='metric': raise ValueError('SI metric units required')
    params={'latitude':latitude,'longitude':longitude,'hourly':','.join(FIELDS),
            'timezone':'UTC','temperature_unit':'celsius','wind_speed_unit':'ms',
            'forecast_days':min(16,max(forecast_days,(hourly_horizon_h+23)//24+2)), 'past_days':1}
    if provider_model!='auto': params['models']=provider_model
    def fetch(p):
        response=requests.get(OPEN_METEO_URL,params=p,timeout=(5,20))
        response.raise_for_status()
        return response.json()
    data=fetch(params)
    hourly=parse_hourly(data)
    for a in arrays or []:
        tilted=fetch({**params,'hourly':'global_tilted_irradiance','tilt':a['tilt_deg'],
                      'azimuth':provider_azimuth(a['azimuth_deg'])})
        merge_poa(hourly,tilted,a['id'])
    daily_data=fetch({**params,'hourly':None,'timezone':timezone,
        'daily':'sunshine_duration,precipitation_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max'})
    d=daily_data.get('daily',{})
    days=[]
    daily_fields={'sunshine_duration':'sunshine_duration_s','precipitation_sum':'precip_day_total_mm',
        'temperature_2m_max':'temp_day_max_c','temperature_2m_min':'temp_day_min_c','wind_speed_10m_max':'wind_day_max_ms'}
    for key,values in d.items():
        if len(values)!=len(d.get('time',[])): raise ValueError('Invalid daily forecast field length')
    for i,date in enumerate(d.get('time',[])):
        row={'date_local':date}
        for key,target in daily_fields.items():
            value=d.get(key,[None]*len(d['time']))[i]
            row[target]=finite(value,key) if value is not None else None
        days.append(row)
    return {'issue_time_utc':iso(dt.datetime.now(dt.timezone.utc)),
            'hourly':hourly,'daily':days}
