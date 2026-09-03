# 工作留痕

这里保存可提交到 Git 的人工工作记录。设备原始运行日志位于 `logs/`，不进入 Git；两者用途不同。

## 三类记录

- `Source: manual`：开发者正常记录自己的修改。
- `Source: terminal`：现场调试期间通过 ARES-R 终端的 `note` 命令记录。
- `Source: reconstructed`：他人完成工作但没有记录，由整理者根据代码、聊天和现场情况事后补录。

## 快速记录

```bash
export ARES_R_AUTHOR="姓名"
./scripts/worklog add "修正 Epic 抓取响应解析" \
  --files src/ares_r/adapters/epic.py \
  --tests "使用三份录包离线验证" \
  --next "现场核对错误码"
```

事后补录：

```bash
./scripts/worklog add "补录：调整左臂观察位" \
  --author "整理人（原工作者：待确认）" \
  --source reconstructed \
  --details "根据现场聊天和配置差异整理，原始操作时间待确认"
```

日志按日期追加到 `worklog/daily/YYYY-MM-DD.md`。不要在记录中写密码、Token 或其他密钥。
