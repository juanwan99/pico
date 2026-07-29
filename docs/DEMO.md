# Pico 独立原型 — 今日演示

```
SCOPE: juanwan99/pico only
PRODUCT: Claude 式 AI 空间 + Kimi Agent + 模型 API + 唯一账本
NOT: 网盘 · 教务 SaaS · edu 联调
```

## 30 秒启动

```bash
# 仓库根目录
cp -n .env.example .env   # 填入 KIMI_API_KEY
make product              # API :8000 + NextChat :8080
```

打开 **http://127.0.0.1:8080**（NextChat 产品壳）

## 现场路径（S1–S7）

| 步 | 操作 | 看见什么 |
|----|------|----------|
| 1 | 左侧 **签发测试凭证**（school-a） | S4 身份 |
| 2 | **一键演示路径** 或「创建任务并运行」 | 多步 tool.call/result + 回复 |
| 3 | 右侧 **产物** | 班级表 markdown |
| 4 | **跨校拒绝 (S6)** | 时间线 `auth.deny` |
| 5 | **新建提案** → **人工确认** | S7 审计；不写学校库 |
| 6 | 顶栏 pill | 危险工具 OFF · Agent pin |

## 无 UI 的证据

```bash
make demo    # scripts/demo_e2e.py → DEMO_OK
make test
make hello   # 真模型或诚实 BLOCKED
```

## 一句话对外

> Pico 是独立 AI 底座原型：服务端 Kimi 多步工具环、真实模型 API、三区 UI、租户 fail-closed 账本；今天不连 edu。
