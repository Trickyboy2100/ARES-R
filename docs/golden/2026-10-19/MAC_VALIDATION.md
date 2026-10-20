# 2026-10-20保全验证

- 原staging不改动；独立分支保存1799个源文件，全部与本地原件SHA256一致。
- Python源文件AST语法检查通过。暂存全部新增文件后，diff --check提示原始preview URDF尾空格、legal_contact.json和test_pregrasp_cache.py尾空行；为逐字节保全原件未做格式改写。这些是归档格式提示，不是测试通过的替代依据。
- 独立Mac虚拟环境：Python3.14、NumPy2.5.4、SciPy1.18.1、PyYAML6.0.3。这不是现场pinned环境，不替代Ubuntu GPU回放。
- `test_roundtrip_demo.py`：17/17通过。
- `test_physical_payload.py`：7/7通过。
- `test_latency_solver.py`：6/6通过。
- 初次尝试因Mac默认Python缺NumPy失败；安装到独立环境后上述30项通过。没有改测试或生产代码以绕过失败。
- 历史现场782项OK/1 skipped的原始记录单独保存，不作为本次重测结果。
- 未连接设备、未运行cuRobo GPU测试、未测试实机，未改变运行参数。
- 全量现场证据不齐；归档状态为PARTIAL，未宣布可独立完整复现。
