# KOH 正式赛积分规则

## 1. 记号与参数

正式赛采用累计积分制，不采用 ELO。

设：

- $t$ 为某一次自动结算时刻
- $R_t$ 为时刻 $t$ 的一次结算
- $U_t$ 为参加 $R_t$ 的有效选手集合
- $N_t = |U_t|$ 为本次结算的有效选手人数
- $M_t$ 为本次结算的有效地图池
- $L_t = |M_t|$ 为本次结算的地图数

固定参数如下：

- 单局基础分：胜 `1`，平 `0.4`，负 `0`
- 地图奖励系数上限：`1.50`
- BP 广度系数范围：`[0.85, 1.15]`
- 主动挑战系数范围：`[0.70, 1.00]`
- 单次结算标准分上限：`10`
- 冷门度统计窗口：最近 $W = 8$ 次已完成结算

除特别说明外，所有动态量均以本次结算开始前的历史数据为准，不使用本次结算中的结果反向影响本次结算的系数。

---

## 2. 有效参赛资格

选手 $u$ 在结算 $R_t$ 中有效，当且仅当在时刻 $t$ 之前同时满足：

- 已提交一份可用的最新进攻模型
- 已提交一份可用的最新防守模型
- 已提交一份可用的 BP 列表

系统在时刻 `t` 读取选手上述三项的最新版本，作为该选手参加 `R_t` 的唯一有效版本。

若 $N_t < 2$，则 $R_t$ 不产生对局，所有选手本次结算得分记为 $0$。

---

## 3. 对局结构

在结算 $R_t$ 中，所有有效选手两两进行一个 `BO2`。

对任意不同选手 $u, v \in U_t$，系统安排两局：

- 第 1 局：`u` 进攻，`v` 防守
- 第 2 局：`u` 防守，`v` 进攻

因此：

- 每对选手恰好进行 `2` 局
- 每名选手在本次结算中共进行 $2(N_t - 1)$ 局

若某局因系统故障未能产生合法结果，则该局按平局计，即双方该局基础分均记为 `0.4`。

---

## 4. BP 有效列表与覆盖度

对选手 $u$，记其提交的原始 BP 列表为 $BP_u$。

系统先对 `BP_u` 做如下处理：

1. 删除不在 `M_t` 中的地图
2. 按原顺序去重，仅保留第一次出现

处理后得到 `u` 在结算 `R_t` 中的有效 BP 列表：

$$
P_t(u) = [m_1, m_2, \ldots, m_k]
$$

其中：

- $k = K_t(u) = |P_t(u)|$
- $0 \le K_t(u) \le L_t$

定义覆盖率：

$$
\operatorname{Cov}_t(u) = \frac{K_t(u)}{L_t}
$$

当 $L_t = 0$ 时，定义 $\operatorname{Cov}_t(u) = 0$。

---

## 5. BP 广度系数

选手 $u$ 在结算 $R_t$ 中的 BP 广度系数定义为：

$$
B_t(u) = 0.85 + 0.30 \cdot \sqrt{\operatorname{Cov}_t(u)}
$$

因此恒有：

$$
0.85 \le B_t(u) \le 1.15
$$

性质：

- 当 $K_t(u) = 0$ 时，$B_t(u) = 0.85$
- 当 $K_t(u) = L_t$ 时，$B_t(u) = 1.15$

该系数只放大已获得的比赛结果，不单独产生积分。

---

## 6. 主动挑战系数

对地图 $m \in M_t$，定义其在 $u$ 的有效 BP 列表中的名次：

- 若 $m = m_r$，则 $\operatorname{rank}_t(u, m) = r$
- 若 $m$ 不在 $P_t(u)$ 中，则 $\operatorname{rank}_t(u, m) = +\infty$

选手 $u$ 在地图 $m$ 上的主动挑战系数定义为：

- 若 $\operatorname{rank}_t(u, m) = +\infty$，则 $A_t(u, m) = 0.70$
- 若 $L_t = 1$ 且 $\operatorname{rank}_t(u, m) = 1$，则 $A_t(u, m) = 1.00$
- 否则

$$
A_t(u, m) = 1.00 - 0.30 \cdot \frac{\operatorname{rank}_t(u, m) - 1}{L_t - 1}
$$

因此恒有：

$$
0.70 \le A_t(u, m) \le 1.00
$$

解释：

- 地图越靠前，`A_t(u, m)` 越高
- 不在 BP 中的地图，按最低系数 `0.70` 计算

---

## 7. 地图冷门度

冷门度仅由历史选图频率决定。

记 $H_t$ 为时刻 $t$ 之前最近 $W$ 次已完成结算的集合。若历史完成结算不足 $W$ 次，则取全部已完成结算。

对地图 $m \in M_t$，定义：

- $\operatorname{PickHist}_t(m)$：在 $H_t$ 中，以 $m$ 作为实际对局地图的 `BO2` 数量
- $\operatorname{TotalHist}_t = \sum_{x \in M_t} \operatorname{PickHist}_t(x)$

若 $\operatorname{TotalHist}_t = 0$，则定义所有地图冷门度均为 $0.5$。

否则定义历史选图频率：

$$
q_t(m) = \frac{\operatorname{PickHist}_t(m)}{\operatorname{TotalHist}_t}
$$

按 $q_t(m)$ 从小到大对 $M_t$ 中所有地图排序。记排序名次为 $\operatorname{cold\_rank}_t(m)$，最冷门的地图名次为 $1$，最热门的地图名次为 $L_t$。若频率相同，则按地图编号升序打破平局。

地图 $m$ 的冷门度定义为：

- 若 $L_t = 1$，则 $\operatorname{Cold}_t(m) = 0.5$
- 否则

$$
\operatorname{Cold}_t(m) = 1 - \frac{\operatorname{cold\_rank}_t(m) - 1}{L_t - 1}
$$

因此恒有：

$$
0 \le \operatorname{Cold}_t(m) \le 1
$$

并满足：

- 最冷门地图的 $\operatorname{Cold}_t(m) = 1$
- 最热门地图的 $\operatorname{Cold}_t(m) = 0$

---

## 8. 地图难度

每张地图 $m$ 具有一个预先公布的静态难度值 $\operatorname{Diff}(m)$，由赛事方确定并固定在区间 $[0, 1]$ 内。

其中：

- $\operatorname{Diff}(m) = 0$ 表示最低难度
- $\operatorname{Diff}(m) = 1$ 表示最高难度

在该值被赛事方更新前，所有结算均使用同一难度值。

---

## 9. 地图奖励系数

地图 $m$ 在结算 $R_t$ 中的地图奖励系数定义为：

$$
\operatorname{Map}_t(m) = \min\left(1.50,\; 1 + 0.25 \cdot \operatorname{Cold}_t(m) + 0.25 \cdot \operatorname{Diff}(m)\right)
$$

因此恒有：

$$
1.00 \le \operatorname{Map}_t(m) \le 1.50
$$

性质：

- 热门且低难地图的系数接近 `1.00`
- 冷门且高难地图的系数接近 `1.50`

---

## 10. 单局基础分函数

对任一单局，记选手 $u$ 的结果为 $\mathrm{res}$，则其基础分为：

- 若 $\mathrm{res} = \text{胜}$，则 $\operatorname{Base}(\mathrm{res}) = 1$
- 若 $\mathrm{res} = \text{平}$，则 $\operatorname{Base}(\mathrm{res}) = 0.4$
- 若 $\mathrm{res} = \text{负}$，则 $\operatorname{Base}(\mathrm{res}) = 0$

该值不依赖对手信息，不依赖地图信息。

---

## 11. 单局得分公式

设结算 $R_t$ 中，选手 $u$ 在地图 $m$ 上进行某一单局，结果为 $\mathrm{res}$。

其单局得分定义为：

$$
\operatorname{GameScore}_t(u, m, \mathrm{res}) = \operatorname{Base}(\mathrm{res}) \cdot \operatorname{Map}_t(m) \cdot B_t(u) \cdot A_t(u, m)
$$

因此：

- 若负，则 $\operatorname{GameScore}_t(u, m, \text{负}) = 0$
- 若平，则 $\operatorname{GameScore}_t(u, m, \text{平}) = 0.4 \cdot \operatorname{Map}_t(m) \cdot B_t(u) \cdot A_t(u, m)$
- 若胜，则 $\operatorname{GameScore}_t(u, m, \text{胜}) = 1.0 \cdot \operatorname{Map}_t(m) \cdot B_t(u) \cdot A_t(u, m)$

对任意单局，单局得分上界为：

$$
1 \cdot 1.50 \cdot 1.15 \cdot 1.00 = 1.725
$$

---

## 12. BO2 得分

对任意一对选手 $u, v$，设其两局比赛使用的地图分别为 $m_1, m_2$，$u$ 的结果分别为 $\mathrm{res}_1, \mathrm{res}_2$，则：

$$
\operatorname{BO2Score}_t(u, v) = \operatorname{GameScore}_t(u, m_1, \mathrm{res}_1) + \operatorname{GameScore}_t(u, m_2, \mathrm{res}_2)
$$

对任意 $u$，其本次结算的原始总分为：

$$
\operatorname{Raw}_t(u) = \sum_{v \in U_t,\; v \ne u} \operatorname{BO2Score}_t(u, v)
$$

---

## 13. 单次结算归一化

由于不同结算的有效人数可能不同，正式计入总榜前需做统一归一化。

对任意选手 $u \in U_t$，其在结算 $R_t$ 中的理论最高原始分为：

$$
\operatorname{RawMax}_t(u) = 2 \cdot (N_t - 1) \cdot 1.725
$$

其中：

- $2 \cdot (N_t - 1)$ 是该选手总局数
- $1.725$ 是单局理论最高分

定义标准化结算分：

- 若 $N_t < 2$，则 $\operatorname{RoundScore}_t(u) = 0$
- 否则

$$
\operatorname{RoundScore}_t(u) = 10 \cdot \frac{\operatorname{Raw}_t(u)}{\operatorname{RawMax}_t(u)}
$$

因此恒有：

$$
0 \le \operatorname{RoundScore}_t(u) \le 10
$$

该值保留到不少于小数点后 `4` 位后再进入累计积分。

---

## 14. 累计积分

选手 $u$ 在全部已完成结算后的累计积分定义为：

$$
\operatorname{TotalScore}(u) = \sum_t \operatorname{RoundScore}_t(u)
$$

求和范围为该选手实际参加过的全部已完成结算。

未参加某次结算时，视为该次结算得分为 `0`，但该次结算不计入其有效参赛次数。

---

## 15. 排名规则

总榜按以下顺序排序：

1. $\operatorname{TotalScore}(u)$ 降序
2. 全部历史单局胜局数降序
3. 全部历史高奖励地图胜局得分总和降序
4. 最近一次已完成结算的 `RoundScore_t(u)` 降序
5. 用户名升序

其中“高奖励地图”定义为满足下式的地图：

$$
\operatorname{Map}_t(m) \ge 1.25
$$

第 3 项中的“高奖励地图胜局得分总和”定义为：

$$
\operatorname{HighMapWinScore}(u) = \sum \operatorname{GameScore}_t(u, m, \text{胜})
$$

求和范围限于所有满足 `Map_t(m) >= 1.25` 的历史胜局。

---

## 16. 特殊情况处理

### 16.1 地图池变更

当地图池发生增删时：

- $M_t$ 与 $L_t$ 以本次结算开始时的有效地图池为准
- 历史冷门度统计仅在 `M_t` 上重新计算，不要求旧结算中的地图池与当前完全一致

### 16.2 BP 为空或无效

若选手具备模型，但其有效 BP 列表 $P_t(u)$ 为空，则：

- 该选手仍可参加结算
- 其 $B_t(u) = 0.85$
- 对任意地图 $m$，其 $A_t(u, m) = 0.70$

### 16.3 历史样本不足

若 $H_t$ 为空，则所有地图：

- $\operatorname{Cold}_t(m) = 0.5$

其他公式保持不变。

### 16.4 结果精度

所有中间计算使用至少双精度浮点数。

展示时可四舍五入；排名比较时使用未展示前的真实值。

---

## 17. 最终执行口径

正式赛结算以平台实际记录的以下数据为准：

- 结算时刻的有效参赛名单
- 结算时刻的选手最新模型与 BP
- 对局实际地图
- 对局实际胜平负结果
- 结算开始前已确定的地图难度值
- 结算开始前的历史冷门度统计

除赛事方明确公告修订外，积分计算一律按本文件公式执行。
