import {h} from './base.js';
import {stats} from './readout.js';
import {status} from './drill_selector.js';
export const fraction = n => `${(100*n).toFixed(1)}%`;
export function renderCurve({curve,median,status:state}) {
  const steps=curve.map(r=>`<li><strong>${h(r.seconds)} 秒</strong>　到达 ${h(r.arrivals)} / 在险 ${h(r.at_risk)}　删失 ${h(r.censored)}
    <meter min="0" max="1" value="${h(r.remaining)}"></meter> 未签到比例 ${fraction(r.remaining)}</li>`).join('');
  return stats([['时效记录',status[state]],['估计中位签到',median==null?'未达到':median+' 秒']])+
    (steps?`<ol class="step-ledger">${steps}</ol>`:'<p class="callout">观测卡齐备后，可封存计算风险集。</p>');
}
