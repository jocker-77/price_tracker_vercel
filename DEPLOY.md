# 部署到 Vercel — 分步指南

## 整体架构
```
你的浏览器 → Vercel（前端 + 后端 API）→ Supabase（数据库）
```
Vercel 负责托管页面和运行 Python 函数，Supabase 负责存储商品数据和价格历史。**两者均有免费套餐，全程零费用。**

---

## 第一步：创建 Supabase 数据库（约5分钟）

1. 打开 https://supabase.com，注册账号（可用 GitHub 登录）
2. 点击「New project」，填写项目名（如 `price-tracker`），选择新加坡节点（离中国最近）
3. 等待项目初始化（约1分钟）
4. 进入项目后，点击左侧菜单「SQL Editor」
5. 把以下代码**完整粘贴**到输入框，点击「Run」：

```sql
-- 商品表
CREATE TABLE products (
  id            SERIAL PRIMARY KEY,
  name          TEXT    NOT NULL,
  jd_url        TEXT,
  jd_sku        TEXT,
  store_type    TEXT    DEFAULT '自营',
  taobao_url    TEXT,
  pdd_url       TEXT,
  target_price  NUMERIC,
  notes         TEXT,
  current_price NUMERIC,
  last_checked  TIMESTAMPTZ,
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  is_active     BOOLEAN DEFAULT TRUE
);

-- 价格历史表
CREATE TABLE price_history (
  id         SERIAL PRIMARY KEY,
  product_id INTEGER REFERENCES products(id),
  price      NUMERIC NOT NULL,
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 设置表（存邮件配置）
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);
```

6. 看到「Success」表示建表成功

**获取 API 密钥：**
- 进入左侧「Settings」→「API」
- 复制 **Project URL**（形如 `https://xxxx.supabase.co`）
- 复制 **anon / public** Key（以 `eyJ` 开头的长字符串）
- 把这两个值先记在记事本里

---

## 第二步：上传代码到 GitHub（约3分钟）

1. 注册 GitHub 账号：https://github.com
2. 点击右上角「+」→「New repository」
   - 仓库名：`price-tracker`
   - 选 Public（免费计划要求）
   - 勾选「Add a README」
   - 点击「Create repository」
3. 点击「uploading an existing file」链接
4. 把 `price_tracker_vercel` 文件夹中的**所有文件**（包括 `api` 子目录）拖入上传区
5. 点击「Commit changes」

---

## 第三步：部署到 Vercel（约3分钟）

1. 打开 https://vercel.com，用 GitHub 账号注册/登录
2. 点击「Add New Project」→ 找到刚才的 `price-tracker` 仓库 → 点击「Import」
3. 保持默认设置，**先不要点 Deploy**
4. 展开「Environment Variables」，添加两个变量：

   | Name | Value |
   |------|-------|
   | `SUPABASE_URL` | 你在第一步复制的 Project URL |
   | `SUPABASE_KEY` | 你在第一步复制的 anon key |

5. 点击「Deploy」
6. 等待约1分钟，出现「Congratulations!」表示部署成功
7. 点击「Visit」即可看到你的网站，URL 形如 `https://price-tracker-你的名字.vercel.app`

---

## 使用说明

**添加商品：**
1. 在京东找到商品页面，复制链接（格式：`https://item.jd.com/XXXXXXXX.html`）
2. 粘贴到左侧输入框，点击「🔍 自动获取商品信息」
3. 确认名称和价格后，可选填目标价格、淘宝/拼多多链接
4. 点击「✅ 加入追踪列表」

**价格监控：**
- 点击「🔄 刷新价格」手动更新所有商品
- 配置邮件后，刷新时若有降价会自动发送提醒

**分享给他人：**
- 把 Vercel 给你的网址发给别人，直接打开即可
- 所有人共享同一个商品列表

---

## 常见问题

**Q: 点「自动获取」没反应或价格显示失败？**
A: 京东价格接口偶有限流，等几秒再试，或手动填写商品名称后直接添加。

**Q: 想让价格每天自动刷新？**
A: Vercel 本身不带定时任务。可以：① 每次打开网站时手动点刷新；② 升级 Vercel Pro 后配置 Cron Jobs（每天定时调用 `/api/refresh`）。

**Q: 数据库免费吗？**
A: Supabase 免费套餐包含 500MB 存储和每月 50 万次请求，日常使用完全够用。

**Q: 多个人添加商品会冲突吗？**
A: 不会，大家共用一个列表，任何人添加的商品所有人都能看到。如果需要分账号隔离，需要后续添加登录功能。
