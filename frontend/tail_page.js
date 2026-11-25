import {waitJob} from './base.js';
import {intro} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {drills,data,save} from './muster_client.js';
import {chooser} from './drill_selector.js';
import {renderCurve} from './tail_curve.js';
import {correctionPanel} from './correction_panel.js';
export async function render(outlet,user) {
  const list=await drills();
  outlet.innerHTML=`${intro('集合时效','同一时刻先计签到，再移除删失。条带展示观测到该刻仍未签到的估计比例。曲线发布后复核员可凭窗内签到原件发起更正。')}
    <form class="toolrow">${chooser(list)}${user.role==='reviewer'?'<button>封存与计算</button>':''}${feedback}</form>
    <div class="series band"></div>
    <div data-correction-panel></div>`;
  const picker=outlet.querySelector('select');
  async function refresh(){
    if(!picker.value)return;
    outlet.querySelector('.series').innerHTML=renderCurve(await data(picker.value,'tail'));
    await correctionPanel(outlet,picker.value,user,refresh);
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async()=>{const job=await save(picker.value,'tail');await waitJob(job.job_id);await refresh();return '时效证据已经生成';});
  await refresh();
}
