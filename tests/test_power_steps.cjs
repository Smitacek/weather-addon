const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('drawn interval-average power has the same energy as its hourly data',()=>{
 const path='weather-dashboard/web/power_steps.js';assert.ok(fs.existsSync(path),'Interval mean path is missing');
 const context={};vm.runInNewContext(fs.readFileSync(path,'utf8'),context);
 const points=context.intervalSteps([
  {interval_start_utc:'2026-10-12T10:30Z',interval_end_utc:'2026-10-12T11:00Z',power_w:2000},
  {interval_start_utc:'2026-10-12T11:00Z',interval_end_utc:'2026-10-12T12:00Z',power_w:1000},
  {interval_start_utc:'2026-10-12T12:00Z',interval_end_utc:'2026-10-12T13:00Z',power_w:null}]);
 let energy=0;for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(a.power_w!==null&&b.power_w!==null)energy+=(b.power_w+a.power_w)/2*(new Date(b.time)-new Date(a.time))/3600000000;}
 assert.equal(energy,2);assert.equal(points.at(-1).power_w,null);
});
