import {intro} from './readout.js';
import {drills,data,save} from './muster_client.js';
import {chooser,kinds,windowDetails} from './drill_selector.js';
import {stamps} from './clock_status.js';
import {feedback,onSubmit,options} from './submit.js';
export async function render(outlet,user) {
  const list=await drills();
  outlet.innerHTML=`${intro('观测计时','签到有实录时刻。只看到观察结束的人员，选择截止时未签到，保留其仍在观察集的事实。')}
    <div class="toolrow">${chooser(list)}</div><div class="split"><div class="clock stack"></div>
    ${user.role==='operator'?`<form class="entry"><h2>登记点名观测</h2><label>记录码<select name="code"></select></label>
    <label>证据类型<select name="kind">${options(Object.entries(kinds))}</select></label><label>计时 / 秒<input type="number" name="seconds" min="1" required></label>
    <button>保存时间</button>${feedback}</form>`:'<aside class="callout">冻结后保留原始抄录，任何补查只能引用观察凭据。</aside>'}</div>`;
  const picker=outlet.querySelector('[name=drill]');
  async function refresh(){
    if(!picker.value)return;
    const row=list.find(r=>r.code===picker.value), people=await data(row.code,'roster');
    outlet.querySelector('.clock').innerHTML=windowDetails(row)+stamps(people);
    const codes=outlet.querySelector('[name=code]');
    if(codes)codes.innerHTML=options(people.map(p=>[p.code,p.code+' · '+p.group_name]));
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async form=>{await save(picker.value,'clock',{...form,seconds:+form.seconds});await refresh();return '计时已保存';});
  await refresh();
}
