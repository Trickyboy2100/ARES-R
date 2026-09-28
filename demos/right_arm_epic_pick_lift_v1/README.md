# right_arm_epic_pick_lift_v1

已现场完成一次的右臂抓取与抬升 Demo。每次运行必须重新检测、重新扫描、重新规划；
`evidence.json` 仅证明该流程曾成功，不能作为下一次运行输入。

ART：

```text
demo list
demo select right_arm_epic_pick_lift_v1
demo show
demo prepare
demo run
demo stop
```

WebUI 可选择、查看和准备 Demo，但监督式实机执行必须回到 ART/TTY 完成。
本 Demo 在抬升 100 mm 后停止，不包含放置。
