# 协作约定

## 开始工作

1. 从最新 `main` 建立短生命周期分支。
2. 明确本次只改哪个设备或流程。
3. 真机调试前确认运行模式、活动机械臂和停止手段。

## 完成工作

1. 运行相关测试。
2. 使用 `./scripts/worklog add` 添加一条工作记录。
3. 检查 `git diff`，确认没有密码、Token、临时日志和大模型文件。
4. 提交 Git，并在 Pull Request 中说明是否接触过真机。

提交前可运行：

```bash
python3 scripts/check_traceability.py --mode staged
```

如果发现别人已经完成工作但没有记录，不改写历史、不猜测细节。使用 `Source: reconstructed` 补录，并明确哪些信息尚未确认。

## 提交信息

建议格式：

```text
<area>: <change>
```

例如：

```text
epic: validate detection response length
task: add grasp verification transition
base: expose navigation cancel command
docs: reconstruct dryer calibration changes
```
