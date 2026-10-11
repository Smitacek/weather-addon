#!/usr/bin/env python3
"""Weather acquisition worker + main-thread minute archive and MQTT lifecycle."""
import datetime as dt
import logging
import queue
import sys
import threading
import time
from pathlib import Path
from addon_config import get_config
from providers.open_meteo import fetch_open_meteo
from mqtt_helper import MQTTPublisher
from solar_archive import SolarArchive
from solar_telemetry import TelemetryCollector
from solar_service import SolarService
from weather_publication import publish_weather
from log_writer import cleanup_logs

VERSION=Path(__file__).with_name('VERSION').read_text().strip()

def main():
    logging.basicConfig(level=logging.INFO,format='[%(levelname)s] %(message)s',stream=sys.stdout)
    try: config=get_config()
    except Exception as exc:
        logging.error('Invalid configuration: %s',exc);return 1
    logging.getLogger().setLevel(getattr(logging,config.log_level.upper(),logging.INFO))
    logging.info('Weather %s starting; solar=%s arrays=%d timezone=%s',VERSION,config.solar_enabled,len(config.pv_arrays),config.timezone)
    collector=TelemetryCollector(config.telemetry_topics,config.telemetry_max_age_s,config.operating_limits_confirmed)
    publisher=None
    if config.mqtt_enabled:
        publisher=MQTTPublisher(config.mqtt_host,config.mqtt_port,config.mqtt_username,config.mqtt_password,
            config.mqtt_topic_prefix,config.site_id,collector,config.update_interval*3)
        publisher.connect()
    archive=None
    if config.solar_enabled:
        try: archive=SolarArchive(config.solar_archive_path)
        except Exception as exc: logging.error('Solar archive initialization failed: %s',exc)
    service=SolarService(config,publisher,archive,collector) if config.solar_enabled else None
    results=queue.Queue(maxsize=1)
    worker=None;next_fetch=next_sample=next_health=0.0
    def acquire():
        try:
            result=fetch_open_meteo(latitude=config.latitude,longitude=config.longitude,
                hourly_horizon_h=config.hourly_horizon_h,forecast_days=config.forecast_days,
                arrays=config.pv_arrays if config.solar_enabled else [],provider_model=config.provider_model,
                timezone=config.timezone,units=config.units)
            results.put((result,None))
        except Exception as exc: results.put((None,str(exc)))
    try:
        while True:
            mono=time.monotonic();now=dt.datetime.now(dt.timezone.utc)
            if publisher and publisher.connected and publisher.discovery_needed and config.ha_discovery_enabled:
                publisher.publish_ha_discovery_extended()
                if service: publisher.publish_solar_discovery()
                publisher.discovery_needed=False
            if (worker is None or not worker.is_alive()) and mono>=next_fetch and results.empty():
                worker=threading.Thread(target=acquire,daemon=True)
                worker.start();next_fetch=mono+config.update_interval
            try:
                forecast,error=results.get_nowait()
                if error:
                    logging.warning('Weather provider failed: %s',error)
                    if service: service.record_error(error)
                else:
                    if service: service.accept_forecast(forecast,now)
                    log_error=publish_weather(forecast,config,publisher,now)
                    if service: service.weather_log_error=log_error
                    if log_error: logging.error('Weather JSONL archive failed: %s',log_error)
                    cleanup_logs(config.log_retention_days)
                    logging.info('Forecast updated: %d intervals',len(forecast['hourly']))
            except queue.Empty: pass
            except Exception as exc:
                logging.error('Forecast processing failed: %s',exc)
                if service: service.record_error(exc)
            if service and mono>=next_sample:
                service.sample(now);next_sample=mono+60
            if service and mono>=next_health:
                service.publish(now);next_health=mono+30
            time.sleep(1)
    except KeyboardInterrupt: return 0
    finally:
        if archive: archive.close()
        if publisher and publisher.client:
            publisher.publish_raw(f'{config.mqtt_topic_prefix}/{config.site_id}/availability','offline',retain=True,qos=1)
            publisher.client.disconnect();publisher.client.loop_stop()

if __name__=='__main__': sys.exit(main())
