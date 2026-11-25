import {h, notice, correctionStates, badge, waitJob} from './base.js';
import {kinds} from './drill_selector.js';
import {corrections, data, openCorrection, retryCorrection} from './muster_client.js';
import {feedback, onSubmit, options} from './submit.js';

export async function correctionPanel(outlet, drillCode, user, onChanged) {
  const host = outlet.querySelector('[data-correction-panel]');
  if (!host || !drillCode) return;
  const [roster, tickets] = await Promise.all([
    data(drillCode, 'roster'), corrections(drillCode),
  ]);
  const canEdit = user.role === 'reviewer';
  host.innerHTML = `<section class="correction band">
    <h2>曲线更正</h2>
    <p class="hint">更正须提交该观察窗全员的窗内签到原件；重算生效前当前曲线保持有效。</p>
    ${canEdit ? `<form class="entry correction-form">
      <label>更正事由<input name="reason" minlength="5" required placeholder="依据卷内签到原件说明更正原因"></label>
      <div class="correction-rows">${roster.map(p => `
        <fieldset class="correction-row" data-code="${h(p.code)}">
          <legend>${h(p.code)} · ${h(p.group_name)}</legend>
          <label>类型<select name="kind">${options(Object.entries(kinds), p.kind)}</select></label>
          <label>秒<input name="seconds" type="number" min="1" max="1800" value="${h(p.seconds ?? '')}" required></label>
        </fieldset>`).join('')}</div>
      <button>发起更正</button>${feedback}
    </form>` : '<p class="callout">仅复核员可发起曲线更正。</p>'}
    <div class="correction-progress"></div>
  </section>`;

  onSubmit(host.querySelector('form'), async form => {
    const observations = [...host.querySelectorAll('.correction-row')].map(row => ({
      code: row.dataset.code,
      kind: row.querySelector('[name=kind]').value,
      seconds: Number(row.querySelector('[name=seconds]').value),
    }));
    const receipt = await openCorrection(drillCode, {reason: form.reason, observations});
    await waitJob(receipt.job_id);
    await onChanged();
    return '更正已处理，曲线与补查资格已按结果切换';
  });

  const progress = host.querySelector('.correction-progress');
  function renderTickets(rows) {
    if (!rows.length) {
      progress.innerHTML = '<p class="empty-state">暂无更正记录。</p>';
      return;
    }
    progress.innerHTML = `<div class="data-frame"><table><caption>更正处理进度</caption>
      <thead><tr><th>单号</th><th>状态</th><th>事由</th><th>复核员</th><th>更新时间</th><th>操作</th></tr></thead>
      <tbody>${rows.map(t => `<tr>
        <td>#${h(t.id)}</td>
        <td>${badge(correctionStates[t.status] || t.status, t.status)}</td>
        <td>${h(t.reason)}${t.detail ? `<br><small class="detail">${h(t.detail)}</small>` : ''}</td>
        <td>${h(t.owner)}</td>
        <td>${h((t.updated_at || '').replace('T', ' ').slice(0, 19))}</td>
        <td>${(canEdit && (t.status === 'failed' || t.status === 'returned'))
          ? `<button type="button" class="quiet" data-retry="${h(t.id)}">重试同一张单</button>` : ''}</td>
      </tr>`).join('')}</tbody></table></div>`;
    progress.querySelectorAll('[data-retry]').forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const receipt = await retryCorrection(drillCode, Number(button.dataset.retry));
          await waitJob(receipt.job_id);
          await onChanged();
          notice(progress, '同一张更正单已重试完成');
        } catch (error) {
          notice(progress, error.message, true);
          button.disabled = false;
        }
      };
    });
  }
  renderTickets(tickets);
}
