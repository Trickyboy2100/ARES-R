# 公开发布记录

- 日期：2026-10-28。
- 仓库：公共 `Trickyboy2100/ARES-R`。
- 独立分支：`codex/data-grasp-20261021-public`。
- 范围：本目录中的两份原始GRASP数据包、索引、说明和校验表。
- 已明确确认允许公开原始现场点云、坐标、设备内网地址及机器人状态。
- 两个压缩包保持原始字节不变，未脱敏重写；压缩包SHA256与Mac源文件一致。
- 发布前扫描195个文本成员，未匹配到私钥、GitHub token、AWS access key、Bearer凭据或指定敏感凭据字段值。此为规则扫描结果，不是全面安全保证。
- 包内相机原始点云哈希与capture/BODY manifest、study observation绑定一致；BODY文件另计算内部SHA256，记录于DATA_INDEX。
- 数据包分别为41,684,942和18,069,187 bytes，使用普通Git binary，不依赖LFS或外部链接。
- 没有修改生产配置、源数据或机器人状态；没有合并生产主线，也未把其他未推送的工作带入此分支。

复现范围是该次GRASP场景数据及原有study证据，不代表此分支同时包含完整现场生产程序/SDK/全部URDF-STL资产。
