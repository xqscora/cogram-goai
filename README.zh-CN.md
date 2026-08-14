# cogram-goai

**三个 agent、五个可复用 skill、一份带引用的记忆，外加一个必须点头的人。**

这是面向软件 issue 的多 agent 闭环参考实现：分诊拆任务，记忆召回**带引用**的旧笔记
（不是一坨无出处的 dump），核查器拒绝没有证据的子任务，没有人批准就不写回。
写回的笔记可以回滚，行还留着，审计链不断。

这是 Cogram 在 GOAI 2026 Agent Infra 赛道的**公开切片**，不是产品本身。
边界见 [docs/SCOPE.md](docs/SCOPE.md)。

[English](README.md) · [架构](docs/ARCHITECTURE.md) · [Skill 契约](docs/SKILL_keyword_recall.md) · [GOAI 对照](docs/GOAI_2026.md)

---

## 安装与运行

```bash
git clone https://github.com/xqscora/cogram-goai.git
cd cogram-goai
pip install -e .

cogram-goai demo --auto-approve --trace run.jsonl
cogram-goai demo --conflict --auto-approve --no-capture
cogram-goai replay --trace run.jsonl
cogram-goai verify-trace --trace run.jsonl --complete
cogram-goai tools
```

需要 Python 3.9+，**零运行时依赖**。

## 闭环

```
issue 文本
   → A1 triage_clerk        拆成 2–3 个带预算的子任务
   → A2 keyword_memory      Skill cogram.keyword_recall
   → context packet         带 id / band / 原因的引用包；只有 high 才自动注入
                            （两条 high 笔记 cause 冲突 → 不自动注入）
   → A3 checklist_verifier  Skill cogram.evidence_bind
   → 人工审批门              没有明确的 yes 就不写
   → A2 追加结构化便签       text / cause / fix
   → 可选 rollback          status=rolled_back，行仍在
```

## Skill

| Skill | 做什么 |
|---|---|
| `cogram.keyword_recall` | 关键词 + **审核过的同义表**（`超时`↔`timeout`）召回便签；输出 evidence band |
| `cogram.evidence_bind` | 子任务 × 证据表 → checklist；缺证据即失败 |
| `cogram.redact` | 写入前抹掉 secret 形状的片段 |
| `cogram.approval_gate` | verified + 人的决定 → 唯一写许可 |
| `cogram.path_guard` | 拒绝看起来像密钥文件的便签库路径 |

`high` band = 命中了人工打的 tag，才会自动注入下一个 agent。没命中 → `fallback: manual_search`，不编造。

## 设计原则

1. **没有人点头就不写。**
2. **没证据的子任务直接失败。** verifier 只问「在不在」，不问「是不是真的」。
3. **只有一个 agent 碰存储。** 回滚也归它。
4. **便签库不能指向密钥。**
5. **召回只会降级，不会幻觉。**
6. **回滚不是删除。**
7. **上下文必须带引用。**

## 测试

```bash
python -m unittest discover tests -v
```

## 许可

Apache-2.0。刻意不包含的东西见 [docs/SCOPE.md](docs/SCOPE.md)。
