'use strict';
let comparisonData=null,comparisonPeriod='day',comparisonPage=false,comparisonRequest=0,comparisonLead=1;
function localToday(tz='Europe/Prague'){return dayKey(0,tz);}
function comparisonMetric(id,value,unit){const el=$(id);el.replaceChildren(document.createTextNode(number(value,unit==='%'?1:2)+' '));const small=document.createElement('small');small.textContent=unit;el.append(small);}
function comparisonState(day){
 if(day.actual_energy_kwh===null)return 'Chybí měření';
 if(day.predicted_energy_kwh===null)return 'Chybí večerní předpověď';
 if(day.coverage_fraction<0.95)return 'Neúplné měření';
 if(day.curtailed_fraction>0)return 'Možné omezení výroby';
 if(day.partial)return 'Dnešek průběžně';
 if(day.eligible_fraction<0.95)return 'Omezení nelze potvrdit';
 return 'Vhodné ke kalibraci';
}
function comparisonPlot(){
 const report=comparisonData;if(!report||!comparisonPage)return;
 const canvas=$('comparison-chart'),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
 canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 const w=rect.width,h=rect.height,pad=48,tz=report.timezone;
 const rows=report.period==='day'?(report.days[0]?.hours||[]).map(r=>({time:r[0],actual:r[1],prediction:r[2],coverage:r[3]})):report.days.map(r=>({time:r.date_local,actual:r.actual_energy_kwh,prediction:r.predicted_energy_kwh,coverage:r.coverage_fraction}));
 ctx.clearRect(0,0,w,h);ctx.font='12px Segoe UI, sans-serif';ctx.fillStyle='#aab8ca';
 if(!rows.length||!rows.some(r=>r.actual!==null||r.prediction!==null)){ctx.fillText('Pro toto období zatím nejsou data',12,h/2);canvas.onmousemove=null;return;}
 const top=Math.max(0.01,...rows.flatMap(r=>[r.actual,r.prediction].filter(v=>typeof v==='number')))*1.15;
 const y=v=>h-40-v/top*(h-60),space=(w-pad-12)/rows.length;
 for(let n=0;n<=4;n++){const v=top*n/4;ctx.strokeStyle='#3a4656';ctx.beginPath();ctx.moveTo(pad,y(v));ctx.lineTo(w-12,y(v));ctx.stroke();ctx.fillStyle='#aab8ca';ctx.fillText(number(v,top<1?2:1),2,y(v)+4);}ctx.fillText('kWh',2,13);
 const label=r=>report.period==='day'?new Intl.DateTimeFormat('cs-CZ',{timeZone:tz,hour:'2-digit',minute:'2-digit'}).format(new Date(r.time)):r.time.slice(8)+'. '+r.time.slice(5,7)+'.';
 const stride=Math.max(1,Math.ceil(rows.length/(w<450?3:7)));
 rows.forEach((r,i)=>{const x=pad+i*space,bar=Math.max(1,Math.min(25,space*0.36));
  for(const [v,c,offset] of [[r.prediction,amber,0],[r.actual,mint,bar+2]]){if(typeof v==='number'){ctx.globalAlpha=r.coverage<0.95?0.45:1;ctx.fillStyle=c;ctx.fillRect(x+2+offset,y(v),bar,h-40-y(v));ctx.globalAlpha=1;}}
  if(i%stride===0){ctx.fillStyle='#aab8ca';ctx.fillText(label(r),Math.min(w-65,x),h-12);}
 });
 canvas.onmousemove=event=>{const x=event.clientX-canvas.getBoundingClientRect().left;const i=Math.min(rows.length-1,Math.max(0,Math.floor((x-pad)/space)));const r=rows[i];setText('comparison-hover',label(r)+' · odhad '+number(r.prediction,3)+' kWh · skutečnost '+number(r.actual,3)+' kWh · pokrytí '+number(r.coverage*100,1)+' %');};
}
function renderComparison(){
 if(!comparisonData)return;const r=comparisonData,s=r.summary;
 setText('comparison-range',r.start_date+' – '+r.end_date+' (konec období nezahrnut)');
 const fresh=$('comparison-fresh');fresh.className='status '+(r.fresh?'good':'bad');fresh.textContent=r.fresh?'Archiv aktuální':'Čekám na čerstvé vyhodnocení';
 comparisonMetric('compare-actual',s.actual_energy_kwh,'kWh');comparisonMetric('compare-prediction',s.predicted_energy_kwh,'kWh');comparisonMetric('compare-difference',s.error_kwh,'kWh');comparisonMetric('compare-coverage',s.coverage_fraction===null?null:s.coverage_fraction*100,'%');
 setText('comparison-note','Porovnatelné dny: '+s.comparable_days+' z '+s.expected_days+'. Odchylka: '+number(s.error_pct,1)+' %. Průměrná absolutní odchylka: '+number(s.mae_kwh,2)+' kWh/den. Procento se nepočítá při nulovém odhadu.');
 setText('comparison-quality',s.curtailed_fraction>0?'V části měření bylo označené možné nebo potvrzené omezení výroby. Tyto úseky se nepoužijí ke kalibraci.':'Bez potvrzených provozních limitů nelze z rozdílu určit příčinu nižší výroby.');
 $('comparison-rows').replaceChildren();r.days.forEach(day=>{const row=document.createElement('tr');const state=comparisonState(day);[day.date_local,number(day.predicted_energy_kwh,2),number(day.actual_energy_kwh,2),number(day.error_kwh,2),number(day.error_pct,1),number(day.coverage_fraction*100,1)+' %',state].forEach((value,index)=>{const cell=document.createElement('td');cell.textContent=value;if(index===6){cell.className='comparison-status'+(!day.comparable?' warn':'');if(day.issued_at_utc)cell.title='Předpověď vydaná '+new Intl.DateTimeFormat('cs-CZ',{timeZone:r.timezone,dateStyle:'short',timeStyle:'short'}).format(new Date(day.issued_at_utc));}row.append(cell);});$('comparison-rows').append(row);});
 setText('comparison-history',r.first_observation_utc?'Minutový archiv se sbírá od '+new Intl.DateTimeFormat('cs-CZ',{timeZone:r.timezone,dateStyle:'medium',timeStyle:'short'}).format(new Date(r.first_observation_utc))+'. Chybějící dny se nedopočítávají. Dnešek je porovnaný pouze do dosud změřeného času.':'Minutový archiv ještě neobsahuje měření.');
 $('correction-rows').replaceChildren();for(const lead of ['1','2','3']){
  const recommendation=r.recommendations?.[lead]||{};const stats=r.days.map(d=>d.horizons?.[lead]).filter(Boolean);const count=stats.reduce((sum,x)=>sum+(x.compared_hours||0),0);
  const mean=key=>count?stats.reduce((sum,x)=>sum+(x[key]||0)*(x.compared_hours||0),0)/count:null;
  const labels={insufficient_data:'Nedostatek vhodných dat',validated:'Ověřeno na pozdějších dnech',not_improved:'Korekce nezlepšila odhad',outside_limits:'Mimo povolený rozsah'};
  const row=document.createElement('tr');['D−'+lead,String(count),number(mean('hourly_mae_kwh'),3),number(mean('hourly_bias_kwh'),3),String(recommendation.eligible_hours||0),number(recommendation.factor,3),labels[recommendation.status]||'Čekám na vyhodnocení'].forEach(t=>{const cell=document.createElement('td');cell.textContent=t;row.append(cell);});$('correction-rows').append(row);
 }
 comparisonPlot();
}
async function refreshComparison(){
 if(!comparisonPage)return;const request=++comparisonRequest;
 try{const response=await fetch('api/comparison?'+new URLSearchParams({period:comparisonPeriod,date:$('compare-date').value,lead:String(comparisonLead)}));if(!response.ok)throw Error();const result=await response.json();if(request!==comparisonRequest)return;comparisonData=result;$('comparison-error').hidden=true;renderComparison();}
 catch(error){if(request!==comparisonRequest)return;$('comparison-error').hidden=false;setText('comparison-error','Porovnání se nepodařilo načíst. Zkontroluj běh Weather a MQTT.');}
}
for(const [id,view] of [['overview-page',false],['comparison-page',true]])$(id).addEventListener('click',()=>{comparisonPage=view;$('overview-view').hidden=view;$('comparison-view').hidden=!view;for(const [key,selected] of [['overview-page',!view],['comparison-page',view]]){$(key).classList.toggle('selected',selected);$(key).setAttribute('aria-pressed',String(selected));}if(view)refreshComparison();else render();});
$('compare-date').value=localToday();$('compare-date').addEventListener('change',refreshComparison);
for(const period of ['day','week','month'])$('compare-'+period).addEventListener('click',()=>{comparisonPeriod=period;for(const p of ['day','week','month']){$('compare-'+p).classList.toggle('selected',p===period);$('compare-'+p).setAttribute('aria-pressed',String(p===period));}refreshComparison();});
function moveComparison(direction){const selected=new Date($('compare-date').value+'T12:00:00Z');if(!Number.isFinite(+selected))return;if(comparisonPeriod==='month'){selected.setUTCDate(1);selected.setUTCMonth(selected.getUTCMonth()+direction);}else selected.setUTCDate(selected.getUTCDate()+direction*(comparisonPeriod==='week'?7:1));$('compare-date').value=selected.toISOString().slice(0,10);refreshComparison();}
$('compare-prev').addEventListener('click',()=>moveComparison(-1));$('compare-next').addEventListener('click',()=>moveComparison(1));$('compare-today').addEventListener('click',()=>{$('compare-date').value=localToday(comparisonData?.timezone);refreshComparison();});window.addEventListener('resize',comparisonPlot);setInterval(refreshComparison,30000);

for(const lead of [1,2,3])$('lead-'+lead).addEventListener('click',()=>{comparisonLead=lead;for(const n of [1,2,3]){$('lead-'+n).classList.toggle('selected',n===lead);$('lead-'+n).setAttribute('aria-pressed',String(n===lead));}refreshComparison();});
