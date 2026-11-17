# 重启后网络排查

2026-11-17，只读诊断；未改动NAT、路由、防火墙、ROS或机器人运动设置。

## 已验证

- Mac 192.168.1.106，工控机wlo1 192.168.1.112，网关192.168.1.1，工控机有线192.168.99.32。
- 重启后iw报告Power save: off，之前的持久省电关闭设置生效。
- WebUI/backend均active；工控机localhost网页200、28,372字节、0.000833秒；Mac同页约5.1465秒。不能归因为网页服务未启动。
- 同轮Mac→网关6包0丢包、均值50.23ms；Mac→工控机6包0丢包、均值278.37ms。
- 工控机→网关5包20%丢包、均值88.38ms；工控机→Mac5包0丢包、均值102.95ms。短测不能当长期统计。
- wlo1使用2.4GHz channel 6，信号-69dBm，双链信号-69/-91dBm；tx retries累计2004、tx packets 12964、tx failed 4。双链差异只能提示现场检查天线/射频，不能据此断定天线故障。重试计数不是丢包率。
- qdisc noqueue、无overlimits/backlog，3秒采样RX约24.7KB/s、TX约4.4KB/s，未观察到工控机本机带宽占满；这不能排除AP其他客户端占用信道。
- MTU1500，默认路由走wlo1，普通local/main路由规则；TLP和power-profiles-daemon inactive。PCI power/control=on表示保持设备活跃，不等于无线Power save开启。
- 网关脚本只MASQUERADE来源192.168.99.0/24的下游流量，Mac→192.168.1.112为本机INPUT路径，不依赖这条FORWARD/NAT。管理员实际iptables/mangle规则核对因SSH中断未完成，不能声称已核实全部防火墙规则。

## 排查中出现的新状态

随后工控机192.168.1.112的ARP变成incomplete，直连及ZeroTier均Host is down；同时间Mac仍在原网段，Mac→网关3包0丢包、均值9.33ms。说明此时无法从Mac解析/到达工控机；具体是工控机Wi-Fi断开、换网/换IP、AP隔离还是设备状态变化，尚需本地状态核实。

一次限速主机发现45秒未完成，已终止。ARP邻居不是路由器在线客户端清单，不能用失败或incomplete条目统计设备数，也不能宣称路由器过载。

## 尚缺与继续入口

需要工控机本地执行：`nmcli -f GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS device show wlo1`。远程恢复后读取本次NetworkManager/iwlwifi日志、实际iptables规则并扫描可见5GHz候选。当前缓存只有一个物理组2.4GHz AP，不应盲设5GHz导致失联。

结论：已验证省电关闭和网页服务正常；主要异常位于工控机无线/AP路径，尚不能确定驱动、射频、AP拥堵或隔离的具体责任。未完成根因修复，未宣称链路恢复。保留现有网关设置，避免通过无证据删除转发或关闭防火墙进一步破坏访问。

## 恢复后的补充与修正

操作员确认此前失联时工控机切换到了其他Wi-Fi；不能将该次失联当成物理组无线故障的独立证据。

恢复后两条SSH路径均成功，物理组IP仍为192.168.1.112。页面一次完整加载1.351636秒；5次ping 0丢包、均值104.069ms。信号-65dBm，协商TX90Mbps/RX81Mbps，省电off，localhost页面0.000526秒。短测有改善，不代表稳定性问题全部解决，也不能把改善归因于后续设置。

管理员实际规则已读取：INPUT/FORWARD/OUTPUT ACCEPT，NAT只有来源192.168.99.0/24经wlo1的MASQUERADE，以及两条上下游FORWARD放行规则；mangle空，无tc filter。未发现阻断/限速WebUI的规则，未修改NAT或防火墙。

内核记录12:49:39 Connection to AP dc:fe:18:f4:4f:33 lost，12:49:56关联另一AP；13:05:14本地主动离开另一AP，13:05:17回到物理组。关联事件不等于已经证明驱动故障；后一次local choice也不能归因为无线质量。

已保存的多个Wi-Fi均允许自动连接且优先级为0。仅将物理组profile（UUID abce343d-c519-4070-97e0-438a56d3b342）的connection.autoconnect-priority从0改为100，保留其他网络可用、未重连、未重启服务。备份：/var/backups/ares-wifi-priority-20261117-131154/before.txt。此项影响未来选网顺序，不保证AP失联时绝不切到备用网络，也不是延迟修复证明。

省电持久设置仍正确；仍需根据持续测试判断2.4GHz无线抖动，当前没有足够证据认定路由器过载或硬件损坏。
