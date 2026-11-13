# 原参考文件分片归档工具

状态：源码与测试已提供，**当前会话未能执行测试**。不依赖python-pptx，不访问网络或设备，不自动Git提交，不更改原文件。

先用Python 3.10或以上运行：

```bash
python3 -m unittest discover \
  -s docs/presentations/20261114_pointcloud_planning_handoff/tools \
  -p 'test_archive_reference_files.py' -v
```

下面从仓库根目录执行。`SOURCE_DIR`应设置为实际获得用户授权的原文件目录，不是凭空假定的下载路径。

```bash
TOOL=docs/presentations/20261114_pointcloud_planning_handoff/tools/archive_reference_files.py
DEST=docs/presentations/20261114_pointcloud_planning_handoff/reference_binary

python3 "$TOOL" pack \
  "$SOURCE_DIR/生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂(1).pptx" \
  "$DEST/template" --chunk-mib 40

python3 "$TOOL" pack \
  "$SOURCE_DIR/20261028-水分细度目标识别与场景自适应规划控制-2(1).pptx" \
  "$DEST/method" --chunk-mib 40

python3 "$TOOL" pack \
  "$SOURCE_DIR/20261028-水分细度目标识别与场景自适应规划控制(1).pptx" \
  "$DEST/large" --chunk-mib 40

python3 "$TOOL" verify "$DEST/template"
python3 "$TOOL" verify "$DEST/method"
python3 "$TOOL" verify "$DEST/large"
```

解包示例：

```bash
python3 "$TOOL" unpack "$DEST/large" \
  /your/authorized/output/20261028-large-restored.pptx
```

每个目录保存manifest.json与顺序字节片，含整文件和每片SHA256。解包验证顺序、大小及全部校验和。**字节片不能单独用PowerPoint打开**；它不把幻灯片按章节拆成多份PPT，优点是完整保留母版、备注、关系和媒体。

归档成功后，应更新06_SOURCE_TRANSFER_STATUS.json的实际SHA256、字节数、路径与状态，再查看git diff。不要将脚本成功运行解释为PPT排版已验收。若目录已存在，工具拒绝覆盖；中途失败的归档没有有效manifest，需先检查后另选新目录，不删除原件。

本仓库public。上传前检查原件的备注、隐藏页、视频、个人信息与不拟公开的材料；不上传字体文件、凭据、无关个人资料。只有确有发布授权的媒体才入库。现有素材图集的发布限制见其README/MANIFEST/PUBLICATION记录。
