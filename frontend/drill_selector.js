import {options} from './submit.js';
import {h} from './base.js';
export function chooser(rows) {
  return `<label>演练记录<select name="drill">${options(rows.map(r=>[r.code,r.code+' · '+r.title]))}</select></label>`;
}
export const kinds={arrived:'有签到时刻',censored:'截止时未签到'};
export const status={open:'登记中',sealed:'已封存，等待计算',calculated:'时效已计算'};
export const windowDetails=record=>`<p class="callout">${h(record.title)} · ${h(record.day)} · 窗口 ${h(record.cutoff)} 秒</p>`;
