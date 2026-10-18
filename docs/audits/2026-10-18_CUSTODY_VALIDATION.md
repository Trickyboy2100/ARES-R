# 首轮保全验证结果

日期：2026-10-18。只验证归档工具与字节完整性，不运行机器人程序。

| 检查 | 结果 |
|---|---|
| 36个tar.gz逐成员读取/重算SHA256 | PASS，23268项；未extract/执行归档文件 |
| 11个完整Git bundle verify | PASS |
| 第12个partial/promisor clone完整bundle | INCOMPLETE，需要远端对象；不伪造PASS |
| 12个原始工作树porcelain前后比较 | PASS，未改变dirty状态 |
| offsets/operations/新RC golden两个文件哈希 | PASS，6项一致；现场未核查 |
| GitHub integration字节SHA256覆盖 | 1548路径，0未解析blob |
| GitHub audit字节SHA256覆盖 | 1624路径，0未解析blob |
| 非驻留占位文件 | 41项，已记缺失，不计入23268项PASS |
| 全量生产测试 / GPU replay / 实机 | NOT_RUN，首轮custody边界 |

机器可读原始结果：私有归档 `CUSTODY_VERIFICATION.json`、`GOLDEN_SHA_VERIFICATION.json`。
完整性通过不代表release、GPU、模型/场景或19阶段运行验收通过。
