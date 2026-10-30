# Toggl 时间记录镜像服务（服务端）

接收 Toggl Desktop 客户端的时间记录并存入 SQLite，用于集中查看多台电脑的计时数据。

- **服务器**：`10.104.23.127`（Ubuntu 26.04.1 LTS，账号 jyf）
- **监听**：`0.0.0.0:8080`
- **推送地址（客户端填写）**：`http://10.104.23.127:8080`
- **依赖**：仅 Python 标准库，**无需 pip 安装任何东西**
- **服务名**：`toggl-mirror`（systemd，已开机自启）

---

## 一、每天怎么用

```bash
/opt/toggl-mirror/bin/mirror-view stats     # 统计概览：条数、累计时长、最后接收时间
/opt/toggl-mirror/bin/mirror-view list 10  # 最近 10 条明细
/opt/toggl-mirror/bin/mirror-view today   # 今天记了多少、合计多久
/opt/toggl-mirror/bin/mirror-view log      # 实时跟踪推送日志（Ctrl+C 退出）
/opt/toggl-mirror/bin/mirror-view health   # 健康检查（不鉴权）
```

`stats` 里的 **「最后接收时间 / 距今 N 秒前」** 最能直接判断推送是否还活着——
数字一直刷新就正常，长时间不动就是断了。

输出示例：

```
记录总数      : 5
  有效记录    : 5
  已删除      : 0
累计记录时长  : 02:09:11 (7751 秒)
最早开始时间  : 2026-10-30 09:02:01
最后接收时间  : 2026-10-30 11:46:22
距今          : 12 秒前
```

**原始命令**（不依赖脚本时）：

```bash
curl -s http://127.0.0.1:8080/v1/stats | jq .
curl -s "http://127.0.0.1:8080/v1/time_entries?limit=10" | jq .
tail -f /opt/toggl-mirror/log/toggl-mirror.log
```

> 本机没装 sqlite3 命令行工具，直接查库用 `python3 -c "import sqlite3; ..."`。

---

## 二、目录结构

所有内容集中在 `/opt/toggl-mirror` 一个目录下，**整体删除即卸载**：

```
/opt/toggl-mirror/
├── bin/
│   ├── toggl_mirror.py    服务端主程序
│   ├── mirror-view        查看工具（Python3，只读打开数据库）
│   └── selftest.py        端到端自检脚本
├── etc/
│   └── toggl-mirror.env   配置：token、时区
├── data/
│   └── mirror.db          SQLite 数据
├── log/
│   └── toggl-mirror.log   运行日志
└── README.md              本文档
```

---

## 三、服务管理

```bash
sudo systemctl status toggl-mirror
sudo systemctl start   toggl-mirror
sudo systemctl stop    toggl-mirror
sudo systemctl restart toggl-mirror
sudo journalctl -u toggl-mirror -f        # systemd 日志
tail -f /opt/toggl-mirror/log/toggl-mirror.log   # 应用日志（含每次推送明细）
```

服务文件：`/etc/systemd/system/toggl-mirror.service`

```ini
[Unit]
Description=Toggl Desktop time entry mirror receiver
After=network.target

[Service]
Type=simple
User=jyf
WorkingDirectory=/opt/toggl-mirror
EnvironmentFile=/opt/toggl-mirror/etc/toggl-mirror.env
ExecStart=/usr/bin/python3 /opt/toggl-mirror/bin/toggl_mirror.py \
    --host 0.0.0.0 --port 8080 --db /opt/toggl-mirror/data/mirror.db
StandardOutput=append:/opt/toggl-mirror/log/toggl-mirror.log
StandardError=append:/opt/toggl-mirror/log/toggl-mirror.log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## 四、配置

`/opt/toggl-mirror/etc/toggl-mirror.env`（当前值）：

```
MIRROR_TOKENS=          # 空 = 不校验，任何来源都能推送（内网自用）
MIRROR_TZ_HOURS=8       # 东八区
```

改完执行 `sudo systemctl restart toggl-mirror`。

### 4.1 鉴权（MIRROR_TOKENS）

- **留空**：不校验，任何客户端都能推（**当前设置**）
- **填值**：只有 api_token 匹配的客户端能推，多个用**空格**分隔

> ⚠️ 多台机器混用时，这里是 401 的高发区。见「六、排障」。

### 4.2 时区（MIRROR_TZ_HOURS）

客户端按 Toggl API v9 协议发送 **UTC** 时间（形如 `2026-10-30T01:05:38Z`），
这是协议约定，不是 bug，改客户端序列化会影响官方同步。

处理方式是**存储保持 UTC 不动**，另存一份本地时间文本：

| 字段 | 示例 | 说明 |
| --- | --- | --- |
| `start_at` | `2026-10-30T01:05:38Z` | 原始 UTC，忠实记录 |
| `local_start` | `2026-10-30T09:05:38+0800` | 供查看的本地时间 |

时区用**固定偏移**换算，不依赖服务器系统时区（本机是 UTC）。
改 `MIRROR_TZ_HOURS` 重启后，**历史记录会自动回填**。

---

## 五、接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查，不鉴权 |
| POST | `/v1/time_entries` | 推送记录（gzip + chunked，Basic 鉴权） |
| GET | `/v1/time_entries` | 查询，支持 `?limit=100&since=<unix>` |
| GET | `/v1/stats` | 统计：条数、总时长、最早/最晚时间 |

推送体是客户端 `TimeEntry::SaveToJSON(9)` 的原始 JSON，服务端按 **guid 幂等 upsert**；
删除事件只更新 `deleted_at`，不覆盖已有内容（避免把描述/时长洗成空）。

查询返回里会附 `local_start` / `local_stop` 两个本地时间字段。

---

## 六、排障

### 6.1 收不到某台电脑的数据

**第一步：看服务端有没有收到请求。**

```bash
grep -a "10.104.58.165" /opt/toggl-mirror/log/toggl-mirror.log | tail -20
```

- **日志里没有这个 IP** → 网络不通（防火墙/网段），或客户端没配地址、没触发推送
- **有请求但返回 401** → 鉴权不匹配，往下看
- **有请求且 200** → 数据已入库，用 `mirror-view list` 查

### 6.2 401 未授权

**根因**：免登录模式的客户端 api_token 固定是 `local-mode`
（客户端 `Context::localUser()` 硬编码），而**登录过账号的客户端用的是该账号的 api_token**。
客户端只在数据库里没有用户时才进免登录模式，有账号就直接沿用账号 token。

服务端日志会直接打印原因（不打印密码）：

```
拒绝未授权请求：来源 10.104.58.165，客户端 api_token=xxxx，服务端允许=local-mode
```

**处理**（三选一）：

1. 把日志里的 token 加进 `MIRROR_TOKENS`（空格分隔多个），重启
2. 清空 `MIRROR_TOKENS` 关闭校验（当前做法）
3. 让那台机器也跑免登录（清掉本地账号）

### 6.3 日志里出现 `Bad request syntax ('103')` 这类 400

这是 401 的**连带现象**：服务端拒绝时没读完 chunked 请求体，keep-alive 下剩余数据
被当成下一个请求解析。已在本次修复（拒绝前先读完 body 并 `Connection: close`）。
如果还出现，说明服务端程序是旧版，重新部署 `bin/toggl_mirror.py`。

### 6.4 服务起不来，报 `argument --token: expected one argument`

**原因**：token 不能写成命令行参数 `--token $MIRROR_TOKENS`。配置留空时 systemd
展开后 `--token` 后面没有值，argparse 直接报错。

**已改为从环境变量读取**。若手动改服务文件，请保持 `ExecStart` 里**不带** `--token`。

### 6.5 时间显示不对

- 显示 UTC：检查 `MIRROR_TZ_HOURS`，改完重启（历史数据会自动回填）
- `mirror-view today` 少算/多算：已改为按 `local_start` 分组。
  用 UTC 的 `start_at` 比日期会**跨日错位**（如北京 07:00 = UTC 前一天 23:00）

### 6.6 运行中记录显示 `-498148:13:38`

Toggl 协议里运行中记录的 `duration` 是**负的开始时间戳**。已修复为按开始时间
推算已运行时长，显示成 `运行中 (00:02:12)`。

---

## 七、本次修订记录

按时间顺序，都是 2026-10-30 完成的：

| 时间 | 修订 | 说明 |
| --- | --- | --- |
| 08:12 | **初始部署** | 目录 `/opt/toggl-mirror`、systemd 服务、开机自启、端口 8080 |
| 09:03 | **新增 `mirror-view`** | 查看工具：stats / list / today / log / health |
| 09:11 | **时区改为本地显示** | 新增 `local_start`/`local_stop` 列 + `MIRROR_TZ_HOURS`；<br>增量迁移并**自动回填历史记录**；<br>`today` 改按本地时间分组（修跨日错位） |
| 11:35 | **401 诊断日志** | 拒绝时打印收到的 api_token，便于把新机器加白名单 |
| 11:35 | **修复 401 后连接错乱** | 拒绝前先读完 chunked body + `Connection: close`，<br>消除 `Bad request syntax` 400 噪音 |
| 11:43 | **token 改环境变量** | 支持空格分隔多个、过滤空值；<br>修复配置留空导致服务起不来的问题 |
| 11:43 | **关闭鉴权** | `MIRROR_TOKENS=` 留空，解决第二台电脑（10.104.58.165）401 |
| 11:50 | **修复运行中时长显示** | 负 duration 改为按开始时间算已运行时长 |

### 数据库迁移机制

`ensure_schema()` 会做增量迁移，**老库直接升级不用重建**：

- 缺列则 `ALTER TABLE` 补上
- 补列后自动回填 `local_start` / `local_stop`
- 迁移动作会写进日志，例如：

```
数据库迁移：time_entries 增加 local_start/local_stop 列
数据库迁移：回填 2 条记录的本地区时间
```

---

## 八、卸载与迁移

**卸载**：

```bash
sudo systemctl disable --now toggl-mirror
sudo rm -f /etc/systemd/system/toggl-mirror.service
sudo rm -rf /opt/toggl-mirror
sudo systemctl daemon-reload
```

**迁移到别的机器**：

```bash
sudo systemctl stop toggl-mirror
tar czf toggl-mirror.tar.gz -C / toggl-mirror
```

拷到新机器后，**数据目录可直接用**，但 systemd 服务文件不随目录打包，
需要按「三、服务管理」里的模板重建：

```bash
sudo tar xzf toggl-mirror.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl enable --now toggl-mirror
```

---

## 九、客户端配置

Toggl Desktop → 设置 → **记录推送** → 填写：

```
http://10.104.23.127:8080
```

客户端免登录模式下会立即生效（配置直接写进库端），不需要重启。
每有一条记录变更（新建/编辑/停止/删除）就推一次，运行中的记录会周期性更新时长。
