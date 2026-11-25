import {h} from './base.js';
import {kinds} from './drill_selector.js';
export function stamps(people) {
  return `<div class="checkline">${people.map(p=>`<article class="tagbox">
   <strong>${h(p.code)}</strong><p>${h(p.group_name)}</p><small>${h(kinds[p.kind]||'等待登记')}${p.seconds==null?'':` · ${h(p.seconds)} 秒`}</small></article>`).join('')}</div>`;
}
