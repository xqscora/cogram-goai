# cogram-goai

**三个小 agent、一个共享便签库，外加一个必须点头的人。**

这是「最小可用多 agent 闭环」的参考实现：一条 issue 进来，一个 agent 把它拆成子任务，
一个 agent 从便签库里召回以前处理类似问题时记下的东西，一个 agent 检查每个子任务是否有
证据，最后由人批准，才允许写回记忆。

全部是纯 Python + 纯 JSON。没有向量、没有模型调用、没有联网。读代码就能预测每一个输出——
这正是目的：它是**教学切片**，不是产品。

[English](README.md) · [架构](docs/ARCHITECTURE.md) · [Skill 契约](docs/SKILL_keyword_recall.md) · [边界](docs/SCOPE.md)

---

## 安装与运行

```bash
git clone https://github.com/xqscora/cogram-goai.git
cd cogram-goai
pip install -e .

cogram-goai demo --auto-approve --trace run.jsonl
```

需要 Python 3.9+，**零运行时依赖**。

## 闭环

```
issue 文本
   → A1 triage_clerk        拆成 2–3 个带预算的子任务
   → A2 keyword_memory      调用 Skill cogram.keyword_recall 查便签库
   → A3 checklist_verifier  每个子任务都必须带证据
   → 人工审批门              没有明确的 yes 就不写任何东西
   → A2 keyword_memory      追加一条便签，让下一次跑得更热
```

每一步都往 trace 里追加一行 JSON，评审可以不依赖总结、直接复原整个 run。

## 三个 agent

| Agent | 职责 | 不能做什么 |
|---|---|---|
| `A1.triage_clerk` | 解析 issue，产出 2–3 个子任务 + 粗预算 | 不碰代码、不碰存储 |
| `A2.keyword_memory` | 调 skill 召回便签；批准后写回一条 | 不做向量检索、不编造便签 |
| `A3.checklist_verifier` | 对照子任务清单核验证据 | 不能自动 merge |

## Skill：`cogram.keyword_recall`

打分方式故意做成**手算可验证**：正文命中一个词 1 分，标签命中一个 2 分，同分按 note id 排序。
中文按字符 bigram 切，所以中英混排的 issue 也能命中，而不需要引入分词依赖。

没命中时返回空列表 + `fallback: "manual_search"`——**绝不编造**。

```bash
cogram-goai contract                       # 打印机器可读契约
cogram-goai skill --issue "上传超时怎么办"
```

## 设计原则

1. **没有人点头就不写。** 不传 approver 时 `approved=None`，无人值守跑不会偷偷长记忆。
2. **没证据的子任务直接判失败。** verifier 只判断证据在不在，不评价质量——看不到的活它不背书。
3. **只有一个 agent 碰存储。** 读写都归 `KeywordMemoryAgent`，另外两个是纯函数。
4. **便签库不能指向密钥。** 路径里含 `.env` / `secret` / `token` / `credential` 等一律拒绝，
   召回不会变成外泄通道。
5. **召回只会降级，不会幻觉。** 没命中就明确报 fallback。

## 测试

```bash
python -m unittest discover tests -v     # 46 个测试，零依赖
```

## 许可

Apache-2.0。本仓库**刻意不包含**的东西见 [docs/SCOPE.md](docs/SCOPE.md)。
