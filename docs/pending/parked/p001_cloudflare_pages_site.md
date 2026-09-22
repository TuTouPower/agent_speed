# p001 Cloudflare Pages 静态公开站与部署管线

- 来源：`docs/plan.md` §2、§6、§8、§10（规划移交）
- 内容：
    - 静态页面：在内部站点仓库 `web/` 或独立前端目录实现静态展示页，直接消费并渲染 `latest.json`，展示列包含 `model`、`effort`、`source`、`harness`、端到端 TPS、生成 TPS、TTFT（注明含思考）、输出 token、账单输入 token，且包含「速度不是能力排名」提示与 GitHub 链接。
    - 部署流程：编写轻量部署流程，使用 `wrangler pages deploy` 将静态页面与最新的 `latest.json` 部署至 Cloudflare Pages。不触发站点仓库 GitHub Actions，不接登录/数据库/计费。
    - 域名与项目名：绑定正式域名并配置 Cloudflare Pages 项目。
    - 为什么现在没做：MVP 阶段优先聚焦评测内核、多 Harness 适配、调度并发控制与数据清洗聚合，公开前端展示与部署暂搁。
- 处理：不办
- 暂搁：MVP 优先聚焦评测调度与数据聚合内核，公开站前端与部署暂搁
