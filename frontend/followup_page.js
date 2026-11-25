import {intro,table} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {drills,data,save} from './muster_client.js';
import {chooser} from './drill_selector.js';
export async function render(outlet,user) {
  const list=(await drills()).filter(r=>r.status==='calculated');
  outlet.innerHTML=`${intro('漏记补查','对截止时刻仍未签到的匿名码记录后续核对任务。已有签到时刻者不进入漏记单。')}
    <div class="toolrow">${chooser(list)}</div><div class="split"><div class="follow band"></div>
    ${user.role==='reviewer'&&list.length?`<form class="entry"><h2>登记补查任务</h2><label>漏记观察码<select name="code"></select></label>
    <label>核对事项<textarea name="action" minlength="5" required></textarea></label><button>登记补查</button>${feedback}</form>`:''}</div>`;
  const picker=outlet.querySelector('[name=drill]');
  async function refresh(){
    if(!picker.value)return;
    const [rows,people]=await Promise.all([data(picker.value,'followup'),data(picker.value,'roster')]);
    outlet.querySelector('.follow').innerHTML=table('已开立补查',['记录码','事项','复核人'],rows.map(r=>[r.code,r.action,r.owner]));
    if(outlet.querySelector('[name=code]')){
      const used=new Set(rows.map(r=>r.code));
      const eligible=people.filter(p=>p.kind==='censored'&&!used.has(p.code));
      const select=outlet.querySelector('[name=code]');
      select.innerHTML=options(eligible.map(p=>[p.code,p.code]))+
        (eligible.length?'':'<option value="" disabled>当前没有可开立补查的记录</option>');
      select.toggleAttribute('disabled',!eligible.length);
      const button=outlet.querySelector('form button');
      if(button)button.toggleAttribute('disabled',!eligible.length);
    }
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async form=>{await save(picker.value,'followup',form);await refresh();return '漏记补查单已登记';});
  await refresh();
}
