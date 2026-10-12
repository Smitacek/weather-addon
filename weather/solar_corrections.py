"""Conservative advisory correction, trained and checked on separate local days."""
import math

def recommend(days):
    result={}
    for lead in ['1','2','3']:
        usable=[]
        for day in sorted(days,key=lambda r:r['date_local']):
            if day.get('partial'): continue
            predictions=day.get('horizons',{}).get(lead,{}).get('hourly_energy_kwh',[])
            pairs=[]
            for r,p in zip(day.get('hours',[]),predictions):
                if r[1] is not None and p is not None and p>=0.02 and r[3]>=0.95 and r[4]>=0.95 and r[5]==0:
                    pairs.append((r[1],p))
            if pairs:usable.append((day['date_local'],pairs))
        item=dict(status='insufficient_data',factor=None,eligible_hours=sum(len(r[1]) for r in usable),eligible_days=len(usable),
                  training_hours=0,validation_hours=0,validation_improvement_pct=None)
        if len(usable)>=7:
            split=min(len(usable)-2,int(len(usable)*0.7))
            train=[p for _,pairs in usable[:split] for p in pairs];test=[p for _,pairs in usable[split:] for p in pairs]
            item.update(training_hours=len(train),validation_hours=len(test),training_end_date=usable[split-1][0],validation_start_date=usable[split][0])
            if len(train)>=30 and len(test)>=10:
                candidate=sum(a for a,p in train)/sum(p for a,p in train)
                raw=sum(abs(a-p) for a,p in test);adjusted=sum(abs(a-p*candidate) for a,p in test)
                improvement=(raw-adjusted)/raw*100 if raw>0 else None
                item['validation_improvement_pct']=improvement
                if not math.isfinite(candidate) or not 0.5<=candidate<=1.5:item['status']='outside_limits'
                elif improvement is not None and improvement>0:
                    item.update(status='validated',factor=round(candidate,4))
                else:item['status']='not_improved'
        result[lead]=item
    return result
