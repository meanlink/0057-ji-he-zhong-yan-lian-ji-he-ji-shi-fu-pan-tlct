# 集合钟 · 演练集合计时复盘

复核已举办的集合演练，区分已签到时刻和观察截止时仍未签到的记录。

**模拟客户**　松桥社区活动中心，三组志愿者与两位演练记录复核员

**现有流程**　工作人员过去在演练后手改点名表。迟到与漏记混淆，观察结束后仍用虚填时刻计算平均，复盘处理意见没有承办凭据。

**业务交接**　演练名单与计时抄录由记录员交复核员。窗口封存后，活动中心按尾部回看行动单。

## 一日工作剧本

1. 15:00 查阅松桥记录 JR-11 的 180 秒观测窗。
2. 15:03 核对四个匿名记录码与分组。
3. 15:10 逐人对照签到和值守观察截止，禁止用超窗签到填补缺失。
4. 15:20 复核封存 JR-11，后台输出风险集。
5. 15:21 查看 60 秒累计签到估计 25%，120 秒估计 75%。
6. 15:25 对尚未签到的证据开立补查记录，关联匿名名单码。
7. 15:30 尝试给已签到成员开补查单并验证拒绝。

## 算法和演示边界

按时刻排序，先计算该时刻签到事件，再移除同时刻右删失样本。Kaplan–Meier 未签到比例以 S(t)=S(t-1)×(1−d/n) 更新。没有达到 50% 时，中位签到时刻留空。

只接收观察截止以内的匿名记录，关注事后数据质量。每个观察窗需登记所有成员的签到或右删失记录。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

- 前端浏览器地址为 `http://127.0.0.1:18451`。
- FastAPI 文档地址为 `http://127.0.0.1:19451/docs`。
- PostgreSQL 本地端口为 `17951`。后端与后台 worker 共用数据库事务和 Redis 健康探测。
- 开发 HTML、CSS、ES modules 后运行 `docker compose up -d --build frontend`。Python 代码修改后运行 `docker compose up -d --build backend worker`。
- `SEED_DEMO` 控制自动填充。可改三项宿主端口、`DEMO_PASSWORD`、`JWT_SECRET`、`POSTGRES_PASSWORD`。持久卷保存业务数据和队列状态。停机并保留数据使用 `docker compose down`。
- 技术栈为 Python 3.11、FastAPI、PostgreSQL 16、Redis 7、Nginx 与原生浏览器 JS。后端业务模块、SQL 迁移都在 `backend/`。界面和交互在 `frontend/`。

| 账号 | 密码 | 典型权限 |
|---|---|---|
| operator@demo.local | Demo2026! | 登记观察时间 |
| reviewer@demo.local | Demo2026! | 封存窗口和登记漏记补查 |
| viewer@demo.local | Demo2026! | 查阅记录和经计算的指标 |

共享角色和任务状态枚举分别位于 `backend/core.py` 的 `ROLES`、`JOB_STATES` 和 `frontend/base.js` 的 `roles`、`jobStates`。数据库检查约束与服务状态以相应 SQL 和模块为准。

许可证见 LICENSE。
