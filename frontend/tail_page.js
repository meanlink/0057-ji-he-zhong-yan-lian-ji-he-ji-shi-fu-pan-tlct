import {waitJob} from './base.js';
import {intro} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {drills,data,save} from './muster_client.js';
import {chooser} from './drill_selector.js';
import {renderCurve} from './tail_curve.js';
export async function render(outlet,user) {
  const list=await drills();
  outlet.innerHTML=`${intro('集合时效','同一时刻先计签到，再移除删失。条带展示观测到该刻仍未签到的估计比例。')}
    <form class="toolrow">${chooser(list)}${user.role==='reviewer'?'<button>封存与计算</button>':''}${feedback}</form><div class="series band"></div>`;
  const picker=outlet.querySelector('select');
  async function refresh(){if(picker.value)outlet.querySelector('.series').innerHTML=renderCurve(await data(picker.value,'tail'));}
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async()=>{const job=await save(picker.value,'tail');await waitJob(job.job_id);await refresh();return '时效证据已经生成';});
  await refresh();
}
