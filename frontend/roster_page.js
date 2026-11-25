import {intro,table} from './readout.js';
import {drills,data,create} from './muster_client.js';
import {chooser,status,windowDetails} from './drill_selector.js';
import {feedback,onSubmit} from './submit.js';

export async function render(outlet,user) {
  const list=await drills();
  outlet.innerHTML=`${intro('演练名册','把观察窗与匿名分组名单一起登记。卷内只保留记录码，便于与签到抄件核对。')}
    <div class="split"><div class="stack roster"></div>${user.role==='operator'?`<form class="entry">
    <h2>登记新观察窗</h2><label>编号<input name="code" required></label><label>主题<input name="title" required></label>
    <label>举办日<input type="date" name="day" required></label><label>截止 / 秒<input type="number" name="cutoff" min="10" max="1800" value="180" required></label>
    <label>匿名码,小组（每行一组）<textarea name="members" required>A-01,暖厅组
A-02,值守组</textarea></label><button>开立名单</button>${feedback}</form>`:'<div class="callout">工作顺序为核对名单、登记时刻、封存窗口、跟进漏记。</div>'}</div>`;
  const host=outlet.querySelector('.roster');
  host.innerHTML=chooser(list)+'<div class="roster-data"></div>';
  const picker=host.querySelector('select');
  async function refresh() {
    if(!picker.value)return;
    const row=list.find(r=>r.code===picker.value);
    const people=await data(row.code,'roster');
    host.querySelector('.roster-data').innerHTML=windowDetails(row)+table(status[row.status],['记录码','名册小组','有观测'],people.map(p=>[p.code,p.group_name,p.kind?'有':'待录入']));
  }
  picker.onchange=refresh;
  onSubmit(outlet.querySelector('form'),async form=>{
    const members=form.members.trim().split(/\r?\n/).map(line=>{const [code,group_name]=line.split(',').map(x=>x.trim());return {code,group_name};});
    const row=await create({...form,cutoff:+form.cutoff,members});list.push(row);picker.add(new Option(row.code+' · '+row.title,row.code));picker.value=row.code;await refresh();return '名册已登记';
  });
  await refresh();
}
