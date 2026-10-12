'use strict';
const $=id=>document.getElementById(id);
const number=(v,d=1)=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('cs-CZ',{maximumFractionDigits:d,minimumFractionDigits:d}):'—';
let data=null, mode='power';
const amber='#f4bc52',blue='#74b8e6',mint='#68c8a5';
function setText(id,value){$(id).textContent=value;}
function dayKey(offset,tz){const now=new Date();const local=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const v=Object.fromEntries(local.map(x=>[x.type,x.value]));const date=new Date(Date.UTC(+v.year,+v.month-1,+v.day+offset));return date.toISOString().slice(0,10);}
function energy(id,value){const el=$(id);el.replaceChildren(document.createTextNode(number(value)+' '));const small=document.createElement('small');small.textContent='kWh';el.append(small);}
function legend(entries){const el=$('forecast-legend');el.replaceChildren();entries.forEach(([label,color])=>{const span=document.createElement('span');span.style.setProperty('--color',color);span.textContent=label;el.append(span);});}
function plot(canvasId,rows,series,unit,hoverId,tz){
 const canvas=$(canvasId),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
 canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);const w=rect.width,h=rect.height,pad=44;
 ctx.clearRect(0,0,w,h);ctx.font='12px Segoe UI, sans-serif';ctx.fillStyle='#aab8ca';
 const valid=rows.filter(r=>series.some(s=>typeof s.value(r)==='number'));
 if(!valid.length){ctx.fillText('Zatím nejsou dostupná data',pad,h/2);canvas.onmousemove=null;return;}
 const min=new Date(rows[0].time).getTime(),max=new Date(rows[rows.length-1].time).getTime();
 const values=valid.flatMap(r=>series.map(s=>s.value(r)).filter(v=>typeof v==='number'&&Number.isFinite(v)));
 const ceiling=Math.max(unit==='V'?50:unit==='kW'?0.1:100,...values)*1.1;
 const x=t=>pad+(new Date(t).getTime()-min)/Math.max(1,max-min)*(w-pad-15);
 const y=v=>h-pad-v/ceiling*(h-pad-20);
 for(let i=0;i<=4;i++){const value=ceiling*i/4;ctx.strokeStyle='#3a4656';ctx.beginPath();ctx.moveTo(pad,y(value));ctx.lineTo(w-15,y(value));ctx.stroke();ctx.fillStyle='#aab8ca';ctx.fillText(number(value,unit==='kW'?2:0),2,y(value)+4);}
 ctx.fillText(unit,3,13);
 const ticks=w<450?1:w<600?2:6;
 for(let i=0;i<=ticks;i++){const t=min+(max-min)*i/ticks;const label=new Intl.DateTimeFormat('cs-CZ',{timeZone:tz,day:'numeric',month:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(t));ctx.fillText(label,Math.min(w-110,Math.max(pad,x(t)-45)),h-10);}
 series.forEach(s=>{ctx.strokeStyle=s.color;ctx.lineWidth=2.5;ctx.beginPath();let pen=false,previous=null;
 rows.forEach(r=>{const value=s.value(r),time=new Date(r.time).getTime();if(typeof value!=='number'||!Number.isFinite(value)){pen=false;previous=null;return;}if(previous!==null&&time-previous>(canvasId==='observed'?120000:4000000))pen=false;if(pen)ctx.lineTo(x(r.time),y(value));else ctx.moveTo(x(r.time),y(value));pen=true;previous=time;});ctx.stroke();});
 canvas.onmousemove=event=>{const px=event.clientX-canvas.getBoundingClientRect().left;const t=min+(px-pad)/(w-pad-15)*(max-min);const nearest=rows.reduce((a,b)=>Math.abs(new Date(a.time)-t)<Math.abs(new Date(b.time)-t)?a:b);setText(hoverId,new Intl.DateTimeFormat('cs-CZ',{timeZone:tz,dateStyle:'short',timeStyle:'short'}).format(new Date(nearest.time))+'  '+series.map(s=>s.label+': '+number(s.value(nearest),(unit==='V'||unit==='kW')?2:0)+' '+unit).join(' · '));};
}
function render(){
 if(!data)return;const p=data.profile||{},health=data.health||{},tz=p.timezone||'Europe/Prague',valid=data.valid;
 $('status').className='status '+(valid?'good':'bad');setText('status',valid?'Předpověď platná':'Předpověď nedostupná');
 setText('site',(p.array_config||[]).map(a=>a.id.toUpperCase()+' '+number(a.capacity_kw)+' kWp').join(' · ')||'Předpověď dostupné výroby a skutečné měření');
 const days=p.daily||[];const tomorrow=days.find(d=>d.date_local===dayKey(1,tz)),after=days.find(d=>d.date_local===dayKey(2,tz));
 const today=days.find(d=>d.date_local===dayKey(0,tz));const remainingRows=(p.intervals||[]).filter(r=>new Date(r.interval_end_utc)>new Date()&&new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(r.interval_start_utc))===dayKey(0,tz));
 const remaining=today?.remaining_complete&&remainingRows.length&&remainingRows.every(r=>r.power_w!==null)?remainingRows.reduce((sum,r)=>sum+r.power_w*Math.max(0,new Date(r.interval_end_utc)-Math.max(Date.now(),new Date(r.interval_start_utc)))/3600000000,0):null;
 energy('today',valid?remaining:null);energy('tomorrow',valid?tomorrow?.energy_kwh:null);energy('after',valid?after?.energy_kwh:null);
 setText('tomorrow-low','Konzervativní scénář '+number(valid?tomorrow?.conservative_energy_kwh:null)+' kWh');setText('after-low','Konzervativní scénář '+number(valid?after?.conservative_energy_kwh:null)+' kWh');
 const entries=(p.array_config||[]).map((a,i)=>[a.id.toUpperCase(),i?blue:amber]);entries.push(['Celkem',mint]);legend(entries);
 const forecastRows=valid?(p.intervals||[]).map(r=>({...r,time:r.interval_start_utc})):[];
 const lines=(p.array_config||[]).map((a,i)=>({label:a.id.toUpperCase(),color:i?blue:amber,value:r=>r.arrays?.[a.id]?.power_w}));lines.push({label:'Celkem',color:mint,value:r=>r.power_w});
 setText('forecast-title','Předpověď výkonu na '+number(forecastRows.length?(new Date(forecastRows.at(-1).interval_end_utc)-new Date(forecastRows[0].interval_start_utc))/3600000:null,0)+' hodin');
 plot('forecast',forecastRows,lines,'W','forecast-hover',tz);
 const rest=data.remaining_today||{};const todayRows=intervalSteps(rest.intervals||[]);
 const todayLines=(p.array_config||[]).map((a,i)=>({label:a.id.toUpperCase(),color:i?blue:amber,value:r=>typeof r.arrays?.[a.id]?.power_w==='number'?r.arrays[a.id].power_w/1000:null}));todayLines.push({label:'Celkem',color:mint,value:r=>typeof r.power_w==='number'?r.power_w/1000:null});
 plot('today-power',todayRows,todayLines,'kW','today-power-hover',tz);
 const peak=rest.peak_at_utc?new Intl.DateTimeFormat('cs-CZ',{timeZone:tz,hour:'2-digit',minute:'2-digit'}).format(new Date(rest.peak_at_utc)):'—';
 setText('today-power-summary','Zbývá přibližně '+number(rest.energy_kwh)+' kWh. Nejvyšší hodinový průměr '+number(rest.peak_power_w===null||rest.peak_power_w===undefined?null:rest.peak_power_w/1000,2)+' kW v intervalu od '+peak+'.');
 const suffix=mode==='power'?'power_w':'voltage_v';plot('observed',(data.observed_series||[]).map(r=>({...r,time:r.ts_utc})),[{label:'FV1',color:amber,value:r=>r.values?.['pv1_'+suffix]},{label:'FV2',color:blue,value:r=>r.values?.['pv2_'+suffix]}],mode==='power'?'W':'V','observed-hover',tz);
 const values=data.observed_fresh?data.observed?.values||{}:{};$('measurements').replaceChildren();
 [['Výkon','power_w','W'],['Napětí','voltage_v','V'],['Proud','current_a','A']].forEach(([label,key,unit])=>{const row=document.createElement('tr');[label,number(values['pv1_'+key])+' '+unit,number(values['pv2_'+key])+' '+unit].forEach(text=>{const cell=document.createElement('td');cell.textContent=text;row.append(cell);});$('measurements').append(row);});
 setText('ac-output','Výstup z měniče: '+number(values.ac_power_w,0)+' W');
 const qualityNames={missing:'Chybějící měření',ambiguous:'Omezení výroby nelze potvrdit',suspected_curtailed:'Podezření na omezení výroby',confirmed_curtailed:'Potvrzené omezení výroby',eligible:'Vzorek vhodný ke kalibraci'};
 setText('quality',data.observed_fresh?(qualityNames[data.observed?.quality]||'Neznámá kvalita měření'):'Měření není aktuální');setText('mapping',health.mapping_confirmed?'Přiřazení polí k FV1/FV2 potvrzené':'Přiřazení JJZ/JV k FV1/FV2 zatím nepotvrzené.');
 const weather=data.weather?.now||{};$('weather').replaceChildren();[['Teplota','temp_2m_c','°C'],['Oblačnost','cloud_cover_pct','%'],['Záření GHI','ghi_w_m2','W/m²'],['Vítr','wind_speed_10m_ms','m/s'],['Srážky','precip_mm','mm']].forEach(([label,key,unit])=>{const term=document.createElement('dt'),value=document.createElement('dd');term.textContent=label;const metric=weather[key];const fresh=metric&&Date.now()-new Date(metric.ts_utc).getTime()<900000;value.textContent=number(fresh?metric.value:null)+' '+unit;$('weather').append(term,value);});
 $('diagnostics').replaceChildren();[['Stáří předpovědi',number(data.age_s===null?null:data.age_s/60,0)+' min'],['Archiv',health.archive_ok?'Ukládání funguje':'Ukládání není ověřené'],['Porovnané hodiny',String(data.evaluation?.comparable_hours||0)],['Hodiny vhodné ke kalibraci',String(data.evaluation?.eligible_hours||0)]].forEach(([k,v])=>{const a=document.createElement('dt'),b=document.createElement('dd');a.textContent=k;b.textContent=v;$('diagnostics').append(a,b);});
 const translated=(p.array_config||[]).filter(a=>!a.geometry_confirmed).map(a=>a.id.toUpperCase()+': sklon '+number(a.tilt_deg,0)+'° a azimut '+number(a.azimuth_deg,1)+'° jsou návrhové parametry.');translated.push('Teplota článků je odhadnutá. Ztráty a lokální stínění zatím nejsou kalibrované.');$('assumptions').replaceChildren();translated.forEach(t=>{const li=document.createElement('li');li.textContent=t;$('assumptions').append(li);});setText('evaluation','Srovnání využívá předpověď vydanou nejméně hodinu před měřením. Omezené a neúplné intervaly se nepoužijí ke kalibraci.');
 $('evaluation-rows').replaceChildren();(data.evaluation?.hours||[]).filter(r=>r.error_kwh!==null&&r.error_kwh!==undefined).slice(-12).forEach(r=>{const row=document.createElement('tr');[new Intl.DateTimeFormat('cs-CZ',{timeZone:tz,day:'numeric',month:'numeric',hour:'2-digit'}).format(new Date(r.interval_start_utc)),number(r.predicted_energy_kwh,3),number(r.energy_kwh,3),number(r.error_kwh,3)].forEach(t=>{const cell=document.createElement('td');cell.textContent=t;row.append(cell);});$('evaluation-rows').append(row);});
 const error=health.archive_error||health.weather_log_error||health.provider_error;$('error').hidden=!error;setText('error',error?'Problém při získání nebo ukládání dat: '+error:'');
}
async function refresh(){try{const [solar,weather]=await Promise.all([fetch('api/solar').then(r=>{if(!r.ok)throw Error('API nedostupné');return r.json();}),fetch('api/now').then(r=>r.json())]);data={...solar,weather};render();}catch(e){$('error').hidden=false;setText('error','Data nelze načíst. Zkontroluj běh doplňků Weather a MQTT.');}}
for(const [id,value] of [['power-tab','power'],['voltage-tab','voltage']])$(id).addEventListener('click',()=>{mode=value;for(const key of ['power','voltage']){$(key+'-tab').classList.toggle('selected',mode===key);$(key+'-tab').setAttribute('aria-pressed',String(mode===key));}render();});
window.addEventListener('resize',render);refresh();setInterval(refresh,15000);
