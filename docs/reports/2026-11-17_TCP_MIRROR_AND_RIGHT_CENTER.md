# TCP镜像与右臂center规范化

版本 `2026.11.17-onsite-ready-mirror-v1.2-tcp`，72项相关离线测试通过；另有4项center入口测试通过。默认TCP匹配可关闭以保留仅关节点模式。工具标定未修改。TCP匹配优先，连杆保持接近镜像，不承诺所有关节点均在2mm内。

TCP镜像约定 `R_goal=S_BODY_Y R_source S_TCP_Y`，TCP X/Z镜像、Y保持右手系。现场点击的 `mirror-1794884831599632509` 已通过真实TCP回读，位置误差1.524mm、朝向误差0.00850°，执行28.18秒。

右臂通过cuRobo和native ServoJ到新center，再规划一次约2mm模型残差补偿。实际BODY TCP `[0.3583103115460162,-0.09000299358957703,1.027839598058544]m`，距中线90.003mm，位置回读误差0.0051mm、朝向误差0.00191°。这是控制器报告，未经独立外部测量。

TCP +X→BODY +X，TCP +Y→BODY -Z，TCP +Z→BODY +Y；TCP X-Z平面水平。名义RPY为[-90°,0°,0°]。

现场named_poses右center和arm_pose_registry的right/center均已更新，左center未改。网页center读取named_poses完整姿态。备份 `worklog/preservation/right-center-normalized-20261117T110942/`，证据 `worklog/evidence/2026-11-17-right-center-normalization/1794884278676811002/`。

现场完整增量归档 `worklog/deploy/20261117-mirror/tcp-center-20261117-evidence.tar.gz`，SHA256 `0209003615ecbf93f14817de49b6713930b5c4cc16571dc42118baba242af63d`。scp拉回遭自动审批服务Bad Request拒绝，归档尚未同步Mac，现场原件完整。本地已记载已知center目标及关节，不能代替完整归档。未push。
