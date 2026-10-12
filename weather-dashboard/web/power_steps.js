'use strict';
// Each mean occupies its entire source interval. Nulls remain explicit gaps.
function intervalSteps(intervals){
 return intervals.flatMap(r=>[{...r,time:r.interval_start_utc},{...r,time:r.interval_end_utc}]);
}
