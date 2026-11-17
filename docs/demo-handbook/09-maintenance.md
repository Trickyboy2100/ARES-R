# 更新机制与下一步

## 文件结构

- `README.md` 入口、状态概述。
- `01-naming.md` 编号与工位约定。
- `catalog.json` 文档目录事实与别名映射。
- `02-catalog.md` 由目录生成的取放/Utility总表。
- `03-fetch.md` 抓取过程与参数。
- `04-place.md` 放置过程与参数。
- `05-utility.md` 通用功能、测试分支、历史Scheme。
- `06-handover.md` 持物高度、转场及跨工位合同。
- `07-delivery.md` 原生到ROS适配与交付。
- `08-evidence.md` 当前参数版本和证据索引。
- `scripts/build_demo_handbook.py` 构建及一致性检查。

## 更新时机

每次完整实机成功、有效参数变更、ROS完整联调或交付包生成后，更新对应条目。未完成实验只更新last_attempt，保留last_full_physical_success。重要阶段结束形成版本与Git提交。

维护者读取真实result/native/controller反馈后，更新catalog状态、参数SHA、证据路径与相应流程文档。构建器负责格式与链接一致性，实机结论由证据审阅产生。网页页头显示文档版本与证据日期，避免静态手册被理解为实时运行状态。

## 本版待办

1. 确认D1筛网/D2料盘命名提案，绑定A0/C0/B1–B3/D1–D2实际站位与SLAM版本。
2. 校正Console筛网全链strategy分派，补充未知strategy拒绝测试。
3. 复用原生下中、专机、筛网天平放置成功记录，接通薄ROS调用。
4. 核对ID2料盘当前V7与11月9日成功运行参数；确认ID9称/程工位身份。
5. 提取独立HOLD出口，定义低层烘干箱entry profile。
6. 将剩余槽位偏置和动作方向写成配置，逐槽验收。
7. 后续给Console卡片显示新编号、文档链接与四个独立状态字段；新编号启动解析通过显式映射实现。

## 维护命令

```sh
python3 scripts/build_demo_handbook.py
python3 scripts/build_demo_handbook.py --check
```

网页产物为单个HTML，支持离线打开和ARES网页路径 `/demo-handbook`。保存 Markdown 与JSON为Git源码，HTML为生成产物。只更新本手册文件时无需读取机器人控制接口。

## 变更记录

2026-11-17 v0.1 建立五位编号、A/R对应表、20项业务取放目录、Utility/测试分支映射、原生实机证据索引、交接高度设计和ROS交付流程。尚未将编号注册为运行alias，尚未据此更改任何物理任务参数。
