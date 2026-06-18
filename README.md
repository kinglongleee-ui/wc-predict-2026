# 🏆 2026 FIFA World Cup Predictor

Multi-agent social simulation → 12 组 + 淘汰赛预测网站。

## 数据来源

MiroFish multi-agent social simulation 跑了 2 轮:
- **Round 3** (run_b37f734df790, 5 rounds 强化约束): 49 场小组赛 + 8 强 4 场 + 4 强 + 决赛 + 5 场冷门
- **Round 2** (run_a18431af48fd, 10,000-iter Monte Carlo): 13 场 + 完整冠军概率表

## 核心预测

- **冠军**: 🇫🇷 法国 (置信度 64%, Round 3)
- **决赛**: 法国 vs 西班牙 (3-2 AET)
- **多轮漂移**: 阿根廷 22% (Round 2) → 法国 64% (Round 3)
- **5 场冷门风险**: Senegal/France, DR Congo/Portugal, Uruguay/Spain, Brazil/Belgium, Mexico/Germany

## 架构

```
数据层   scripts/parse-report.py  MiroFish verdict.json + report.md 
                                → data/runs/{run_id}.json

前端     Next.js 14 (App Router) + TypeScript + Tailwind + react-markdown
         /              首页: 冠军 + 5 场冷门 + 12 组概览
         /groups        12 个组 (A-L)
         /groups/[L]    单组详情 + 全部比赛
         /simulations   Round 2 vs Round 3 对比
         /report/[id]   完整报告 (markdown 渲染)
```

## 本地开发

```bash
# 1. 解析 MiroFish 数据 (一次性, 数据更新时重跑)
npm run parse

# 2. 装依赖 (注意: 设 NODE_ENV=development 让 npm 装 dev deps)
NODE_ENV=development npm install --include=dev

# 3. 开发模式
npm run dev   # http://localhost:3000

# 4. 生产构建
npm run build && npm start
```

## 部署

推荐 Vercel (免费):
1. 推到 GitHub: `git push origin main`
2. Vercel → "Import Project" → 选 GitHub 仓库
3. 自动检测 Next.js, 点 Deploy
4. 5 分钟拿到 `https://wc-predict-xxx.vercel.app`

## 自动更新

cron 每日跑:
```bash
cd ~/wc-predict && npm run parse  # 重解析最新 MiroFish 输出
cd ~/wc-predict && git add data/ && git commit -m "data: refresh $(date -I)"
cd ~/wc-predict && git push  # Vercel auto-deploy
```
