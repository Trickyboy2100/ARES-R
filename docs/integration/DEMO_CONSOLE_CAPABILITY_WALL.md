# Demo Console 功能墙

2026-11-17。默认入口 `/demo-console`，顶部切换“功能墙”和“运行监控”。

## 交付与开发模式

交付模式为默认值。当前明确登记可用的原生项为AAWU0-01、AAWU0-02、AB2P5、AD1P0、AC0P0，仍需后端实际注册且execution_ready有效。其他候选项保留灰色卡片。开发模式可启动已接入的候选入口，现有后端任务与执行校验继续生效。

开发模式提供JSON草稿编辑、浏览器保存和导出，用于配置与调试交接；运行参数由任务既有parameters文件绑定，草稿需审阅后接入。

原生/ROS切换显示对应编号、Action与状态，网页ROS Action桥接尚待接入。选择ROS时当前各项网页启动保持灰色，已交付客户端仍按既有Action调用。开发模式是界面工作方式，不充当用户权限认证。

## 使用方式

1. 在功能墙按取、放、Utility、完整流程、测试分支选择大卡片；可按工位或编号搜索。
2. 每张卡片显示A/R编号、对象、动作流程、原生实机结论、ROS交付状态。
3. 选中后右侧查看参数与证据详情，顶部核对准备条件；完整的既有任务说明可展开。
4. 现有原生入口已接入时，完成准备确认后使用顶部按钮启动。启动成功自动切换运行监控。
5. 待接入功能仍可选择、阅读手册与待办。独立Fetch持稳出口与原位抓放测试分支有各自卡片。
6. 运行监控保留三维点云/机械臂/轨迹、阶段计时、事件、系统资源和镜像工具。停止按钮始终位于页头。

交付模式开放当前已确认原生入口，其余灰色卡片仍可阅读。开发模式开放已接入候选入口，提供JSON草稿保存和导出。草稿存储在本机浏览器，修改执行参数需要后续审阅与正式绑定。开发模式属于界面工作流选择，后端现有任务合同继续执行。

原生 / ROS调用切换同时改变编号和入口解析。当前ROS网页Action桥接尚未接入，因此ROS选择可查阅既有Action与交付状态，网页启动保持不可用。

功能墙显示R编号及ROS状态。网页启动沿用canonical原生Console路径，ROS实际Action调用及交付资料通过手册查阅。进入页面、筛选、选中卡片均只读取资料；执行仍需准备确认与启动按钮。

## 当前目录

30项，包括20项业务取放、5项Utility、3项原位抓放/历史抓取测试分支、2项跨工位流程。后端额外出现但未归类的入口显示在“其他已接入”，防止新入口在分类更新前丢失。

目录来自 `docs/demo-handbook/catalog.json`，构建命令 `python3 scripts/build_demo_wall.py`；生成 `src/ares_r/webui/demo_wall_catalog.json`。新增状态先更新手册源，再构建手册和功能墙。原生完整成功、当前参数绑定、ROS适配和Delivered分别维护。

## 入口绑定

`launch_alias`显式指向现有运行时alias，只有运行时实际注册且execution_ready有效时提供启动。

- AA0F0/AC0F0独立持物结束功能暂未接入，不将它们委派为原位抓放。
- AA0F0-03与AC0F0-02分别对应历史料盘HOLD和筛网原位抓放。
- S-C0-D1-01完整筛网流程等待分派修复；可查看任务定义。
- 下中AB2P5对应已成功的 `demo-2-liaopan-placeto-hongganxiang`。

编号映射不会增加另一套规划或设备控制代码。

## 文件与维护

- 页面 `src/ares_r/webui/demo_console.html`。
- 组件 `src/ares_r/webui/demo_wall.js`、`demo_wall.css`。
- 只读目录接口 `GET /api/demo-console/capabilities`。
- 构建器 `scripts/build_demo_wall.py`，检查使用 `--check`。
- 回归 `tests/test_demo_wall.py`，离线浏览器检查包括选择不POST、待接入不可启动、精确alias、筛选、视图切换与模拟启动。

页面的最新任务状态来自canonical现有API，功能验收文字为2026-11-17证据快照。后续完成实机或ROS里程碑后更新目录。

现场逐项调试表位于 `docs/work_orders/2026-11-18_FUNCTION_CONSOLE_COMMISSIONING.md`。
