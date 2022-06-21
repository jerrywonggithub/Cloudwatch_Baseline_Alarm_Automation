# Cloudwatch_Baseline_Alarm_Automation

>此方案目的为了协助运维工程师在 AWS 上能快速建立服务监控基线

### 架构图

![架构图](https://github.com/jerrywonggithub/Cloudwatch_Baseline_Alarm_Automation/blob/main/cw_alarm_automation_architecture.png)
### 方案说明

此方案实现：

1. 协助运维快速建立服务监控基线 - 自动化批量创建 AWS Cloudwatch 指标告警（当前项目先提供 EC2、ElastiCache、RDS 的样例代码，后续会按需逐步更新常用服务）
2. 服务发现，自动添加新增服务（实例）的告警
3. 自定义告警通知信息
4. 接入飞书/微信/钉钉/Slack/其他Webhook端（本样例采用飞书作为演示）

### 指标说明

1. EC2：实例 CPU（百分比）
2. ElastiCache：Redis 引擎 CPU（百分比）、Redis 引擎占用内存（百分比）
3. RDS：实例 CPU（百分比）、实例可用内存（容量）、实例可用存储（容量）、数据库连接数


