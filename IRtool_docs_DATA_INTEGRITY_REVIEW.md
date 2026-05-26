# IRtool 核心功能数据完整性 & 准确性审查报告

> 审查日期：2026-05-26
> 修订日期：2026-05-26（经源码交叉验证后修正）
> 审查范围：网络监控、日志采集（Sysmon）、持久化检测（Autoruns）
> 审查重点：数据完整性、数据准确性

---

## 目录

- [一、网络监控模块](#一网络监控模块)
- [二、日志采集模块（Sysmon）](#二日志采集模块sysmon)
- [三、持久化检测模块（Autoruns）](#三持久化检测模块autoruns)
- [四、跨模块共性问题](#四跨模块共性问题)
- [五、问题严重性汇总](#五问题严重性汇总)
- [六、优先修复建议](#六优先修复建议)

---

## 一、网络监控模块

> 涉及文件：`core/network_monitor.py`、`ui/network_tab.py`

### 🔴 严重问题

#### 1. 连接时间戳是"刷新时刻"而非"建立时刻"

- **位置**：`core/network_monitor.py` 第 76-79 行
- **现状**：

  ```python
  now = datetime.now()
  nc = NetworkConnection(
      timestamp=now.strftime("%Y/%m/%d %H:%M:%S"),
      timestamp_epoch=now.timestamp(),
      ...
  )
  ```

- **问题**：`psutil.net_connections()` 不提供连接建立时间，每次刷新都会用 `datetime.now()` 重新生成时间戳。所有连接的时间戳都是"最后一次被观测到的时间"，而非连接实际建立时间。
- **影响**：在应急响应时间线分析中，这会导致严重误判。例如一个已建立数小时的连接，每次刷新都会显示为"刚刚"。
- **建议**：引入 `first_seen_epoch` / `last_seen_epoch` 双时间戳机制：

  1. `NetworkConnection` 模型增加 `first_seen_epoch: float` 和 `last_seen_epoch: float` 字段
  2. `network_monitor.py` 中首次创建连接时，`first_seen_epoch = last_seen_epoch = now.timestamp()`
  3. `network_tab.py` 缓存命中时，只更新 `last_seen_epoch`，不更新 `first_seen_epoch`
  4. UI 显示时间使用 `first_seen_epoch`（首次发现时间），历史清理基于 `last_seen_epoch`（最后观测时间）
  5. 当连接从当前快照消失后，`last_seen_epoch` 不再更新，历史清理可正确判断过期

  ```python
  # network_monitor.py — 构建连接对象
  now = datetime.now()
  epoch = now.timestamp()
  nc = NetworkConnection(
      timestamp=now.strftime("%Y/%m/%d %H:%M:%S"),
      timestamp_epoch=epoch,
      first_seen_epoch=epoch,
      last_seen_epoch=epoch,
      ...
  )

  # network_tab.py — 缓存命中时
  cached['last_seen_epoch'] = conn['last_seen_epoch']
  cached['status'] = conn['status']
  # first_seen_epoch 不更新

  # network_tab.py — 历史清理
  conn_last_seen = cached.get('last_seen_epoch')
  if conn_last_seen and datetime.fromtimestamp(conn_last_seen) < retention_threshold:
      keys_to_remove.append(key)
  ```

---

### 🟡 中等问题

#### 2. PID 复用导致进程信息错乱

- **位置**：`core/network_monitor.py` 第 104-130 行
- **现状**：进程信息缓存 TTL 为 5 秒，缓存结构为 `{PID: (name, path, timestamp)}`
- **问题**：Windows PID 可被复用。5 秒窗口内旧进程退出、新进程获得相同 PID 时，缓存返回旧进程的名称和路径。
- **影响**：显示的进程名/路径与实际进程不匹配，可能误导分析人员。
- **建议**：缓存中同时存储 `proc.create_time()`，获取进程信息时校验进程创建时间是否匹配。如果不匹配，强制刷新缓存。

---

#### 3. 过滤掉 PID 为 None 的连接可能遗漏关键线索

- **位置**：`core/network_monitor.py` 第 51-52 行
- **现状**：

  ```python
  if conn.pid is None:
      continue
  ```

- **问题**：在应急响应中，"无主连接"反而可能是高度可疑的（如 rootkit 隐藏进程、驱动级网络活动）。
- **影响**：遗漏潜在恶意连接。
- **建议**：保留 PID 为 None 的连接，用特殊标记替代过滤：

  ```python
  if conn.pid is None:
      pid = 0
      proc_name = "[无进程]"
      proc_path = "[无进程]"
  else:
      pid = conn.pid
      proc_name, proc_path = self._get_process_info(conn.pid)
  ```

---

## 二、日志采集模块（Sysmon）

> 涉及文件：`core/sysmon/parser.py`、`core/sysmon/subscriber.py`、`core/sysmon/models.py`、`ui/log_collector_tab.py`

### 🔴 严重问题

#### 4. 事件解析失败时完全静默丢弃 — 无任何记录

- **位置**：`core/sysmon/parser.py` 第 34-35 行、第 63-64 行
- **现状**：

  ```python
  # parse_event
  except Exception:
      return None

  # parse_event_with_record_id
  except Exception:
      return None, None
  ```

- **问题**：解析失败的 Sysmon 事件被完全丢弃，没有任何日志记录。调用方无法知道有多少事件解析失败。
- **影响**：在应急响应场景下，丢失任何事件都可能导致遗漏关键攻击线索，且用户完全无感知。攻击者可能构造畸形事件来触发解析异常，从而隐藏自身活动。
- **建议**：
  1. 解析失败时至少保留原始 XML 数据作为 `raw_data`，返回一个基础 `SysmonEvent` 对象
  2. 记录警告日志，包含事件 ID 和异常信息
  3. 在 UI 中标记解析失败的事件

  ```python
  except Exception as e:
      logger.warning(f"[SysmonEventParser] Failed to parse event: {e}")
      return SysmonEvent(
          event_id=0,
          timestamp="",
          timestamp_epoch=0,
          raw_data={"_parse_error": str(e), "_raw_xml": event_xml}
      )
  ```

---

#### 5. 时间戳解析失败时回退为 `datetime.now()` — 破坏时间线

- **位置**：`core/sysmon/parser.py` 第 71 行、第 105 行
- **现状**：

  ```python
  # _parse_system_data 第 71 行 — 默认值
  timestamp = datetime.now()

  # _parse_timestamp 第 105 行 — 解析失败回退
  return datetime.now()
  ```

- **问题**：存在两处 `datetime.now()` 回退：
  1. `_parse_system_data` 中 `timestamp` 初始值为 `datetime.now()`，当 `TimeCreated` 元素不存在或无 `SystemTime` 属性时，直接使用当前时间
  2. `_parse_timestamp` 中所有格式解析失败后，回退为 `datetime.now()`
- **影响**：错误的时间戳比没有时间戳更危险——它会混入正常数据中难以被发现。应急响应中时间线分析是核心，错误的时间戳会导致完全错误的攻击时间线。
- **建议**：两处均改为返回特殊标记，在 UI 中明确标注"时间未知"：

  ```python
  # _parse_system_data
  timestamp = datetime(1970, 1, 1)  # epoch=0，表示时间未知

  # _parse_timestamp
  return datetime(1970, 1, 1)  # epoch=0，UI 中可特殊处理
  ```

  同时在 `NetworkConnection`/`SysmonEvent` 模型中增加 `timestamp_valid: bool` 字段，UI 中对 `timestamp_valid=False` 的事件显示"时间未知"。

---

#### 6. 事件去重键精度不足 — 高频事件可能被错误去重

- **位置**：`ui/log_collector_tab.py` 第 1239-1244 行
- **现状**：

  ```python
  def _make_event_key(ev):
      return (
          getattr(ev, 'timestamp_epoch', 0),
          getattr(ev, 'event_id', 0),
          getattr(ev, 'process_id', getattr(ev, 'source_process_id', 0)),
      )
  ```

- **问题**：去重键仅包含 `(timestamp_epoch, event_id, process_id)`。`timestamp_epoch` 是浮点数，同一毫秒内同一进程的多个相同类型事件会产生相同的去重键。
- **影响**：同一进程在同一毫秒内发起多个 DNS 查询（如解析 `evil.com` 和 `cdn.evil.com`），只会保留一个。在 DNS 隧道检测场景下，这会严重降低检测率。
- **建议**：去重键增加更多维度，根据事件类型包含不同的特征字段：

  ```python
  def _make_event_key(ev):
      base_key = (
          getattr(ev, 'timestamp_epoch', 0),
          getattr(ev, 'event_id', 0),
          getattr(ev, 'process_id', getattr(ev, 'source_process_id', 0)),
      )
      if isinstance(ev, DnsEvent):
          return base_key + (ev.query_name,)
      elif isinstance(ev, NetworkConnectEvent):
          return base_key + (ev.destination_ip, ev.destination_port)
      elif isinstance(ev, CreateRemoteThreadEvent):
          return base_key + (ev.target_process_id, ev.start_address)
      elif isinstance(ev, FileCreateEvent):
          return base_key + (ev.target_filename,)
      return base_key
  ```

---

#### 7. Sysmon 时间戳使用 UTC，网络监控使用本地时间 — 时区不一致

- **位置**：`core/sysmon/parser.py` 第 93-94 行、`core/network_monitor.py` 第 78 行
- **现状**：
  - Sysmon：`dt = dt.astimezone(timezone.utc).replace(tzinfo=None)` — 将时间转为 UTC naive datetime
  - 网络监控：`datetime.now()` — 使用本地时间
  - 两者格式化后的字符串格式相同：`"%Y/%m/%d %H:%M:%S"`
- **问题**：两个模块的时间戳不在同一时区，格式却相同，无法区分。在中国时区（UTC+8），Sysmon 事件会比网络连接时间早 8 小时。
- **影响**：在跨模块时间线分析时，Sysmon 事件和网络连接的时间会有 8 小时偏差。例如，一个 Sysmon 网络连接事件显示 08:00，而同一时刻的网络监控连接显示 16:00，分析人员可能误判为不同事件。
- **建议**：统一使用本机时间显示。在 `_parse_timestamp` 中将时间转为本地时间：

  ```python
  dt = dt.astimezone()  # 转为本机时间，而非 UTC
  return dt.replace(tzinfo=None)
  ```

  全项目时间戳策略：所有模块统一使用本机时间（如北京时间 UTC+8），格式 `"%Y/%m/%d %H:%M:%S"`，不在时间戳字符串中标注时区（因为全部统一为本机时间，无需额外标注）。

---

### 🟡 中等问题

#### 8. 超过 50000 条事件时旧事件永久丢失

- **位置**：`ui/table_model.py` 第 7 行、`ui/log_collector_tab.py` 第 847-854 行
- **现状**：`MAX_ROWS = 50000`，超限时截断 `all_events` 列表
- **问题**：长时间采集场景下，早期事件永久丢失，无法恢复。在应急响应中，早期事件往往包含攻击入口的关键信息。
- **影响**：攻击者可通过大量噪声事件冲刷掉早期关键事件。
- **建议**：实现磁盘溢出机制，超限事件写入临时文件（如 SQLite 或 JSONL），而非直接丢弃。提供"加载更多"功能回溯历史事件。

---

#### 9. DataStore 中 Sysmon 事件无去重

- **位置**：`core/data_store.py` 第 40-43 行
- **现状**：

  ```python
  def add_sysmon_event(self, event):
      self._sysmon_events.append(event)
      self.sysmon_event_added.emit(event)
  ```

- **问题**：加载历史事件后，DataStore 中可能存在重复事件。`add_sysmon_event` 只追加，不检查是否已存在。
- **影响**：跨模块查询时返回重复结果，影响数据准确性。
- **建议**：在 `add_sysmon_event` 中增加去重逻辑，或使用 `set_sysmon_events` 批量替换。

---

#### 10. FileCreateEvent 统一显示为"DLL创建"

- **位置**：`ui/log_collector_tab.py` 第 939-960 行
- **现状**：所有 `FileCreateEvent` 的事件类型显示为 `"DLL创建"`
- **问题**：只有启用 `file_create_dll` 时 Sysmon 配置才会过滤仅 DLL 文件，但如果同时启用了 `file_create`，非 DLL 文件也会被标记为"DLL创建"。
- **影响**：非 DLL 文件被错误标记，误导分析人员。
- **建议**：根据 `target_filename` 后缀动态判断显示类型：

  ```python
  if isinstance(event, FileCreateEvent):
      if event.target_filename.lower().endswith('.dll'):
          event_type_display = "DLL创建"
      else:
          event_type_display = "文件创建"
  ```

---

## 三、持久化检测模块（Autoruns）

> 涉及文件：`core/autoruns_parser.py`、`ui/autoruns_tab.py`

### 🔴 严重问题

#### 11. 服务名称提取逻辑可能导致服务删除失败

- **位置**：`core/autoruns_parser.py` 第 305-307 行
- **现状**：

  ```python
  if category == 'Services':
      service_name = entry_name
  ```

- **问题**：服务名称直接使用 `entry_name`（条目名称），但 autorunsc 输出的 Entry 列可能是服务的**显示名**而非**服务名**。Windows 服务的显示名和服务名可以不同：
  - 显示名：`Windows Update`
  - 服务名：`wuauserv`
- **影响**：`_delete_service` 使用 `sc delete <service_name>` 时，如果传入的是显示名而非服务名，通常会导致**删除失败**（`sc delete` 报"指定的服务不存在"）。在极少数情况下，如果显示名恰好与另一个服务的服务名相同，可能误删该服务。
- **建议**：
  1. 从 `launch_string` 或注册表路径中提取真实的服务名
  2. 使用 `sc query` 验证服务名是否存在
  3. 删除前增加二次确认，显示服务名和显示名

---

### 🟡 中等问题

#### 12. publisher 和 company 字段映射到同一 CSV 列

- **位置**：`core/autoruns_parser.py` 第 314-316 行
- **现状**：

  ```python
  publisher=row.get('Company', '').strip() if row.get('Company') else '',
  company=row.get('Company', '').strip() if row.get('Company') else '',
  ```

- **问题**：两者都映射到 `row.get('Company', '')`。autorunsc 标准 CSV 输出**没有 `Publisher` 列**（标准列为：Entry, Entry Location, Time, Enabled, Category, Description, Company, Image Path, Version, Launch String, MD5, SHA-256, Signer），因此 `publisher` 和 `company` 在当前数据源下实际是同义的。
- **影响**：两个字段值始终相同，`publisher` 字段无独立信息。
- **建议**：保持 `publisher` 映射 `Company`（与 `company` 同义），但在模型注释中明确说明：在 autorunsc 数据源下 `publisher` 和 `company` 是同义的。如果未来引入其他数据源（如 sigcheck 输出）有 `Publisher` 列，再分别映射。

  ```python
  # autorunsc CSV 无 Publisher 列，publisher 与 company 同义
  publisher=row.get('Company', '').strip() if row.get('Company') else '',
  company=row.get('Company', '').strip() if row.get('Company') else '',
  ```

---

#### 13. signer 和 signer_status 字段映射混乱

- **位置**：`core/autoruns_parser.py` 第 320-323 行
- **现状**：

  ```python
  signer=row.get('Signer', '') if row.get('Signer') else '',
  signer_status=row.get('Signer', '').strip() if row.get('Signer') else '',
  ```

- **问题**：
  1. 两者都映射到 `row.get('Signer', '')`，值完全相同
  2. `signer` 不做 strip，`signer_status` 做 strip，处理不一致
  3. Autoruns 的 Signer 列格式通常是 `"Microsoft Corporation (Verified)"`，应拆分为签名者和签名状态
- **影响**：签名者和签名状态信息丢失，无法区分"谁签的名"和"签名是否有效"。
- **建议**：从 Signer 字段中提取签名者名称和验证状态：

  ```python
  raw_signer = row.get('Signer', '').strip() if row.get('Signer') else ''
  if '(Verified)' in raw_signer:
      signer = raw_signer.replace('(Verified)', '').strip()
      signer_status = '(Verified)'
  elif '(Error)' in raw_signer:
      signer = raw_signer.replace('(Error)', '').strip()
      signer_status = '(Error)'
  else:
      signer = raw_signer
      signer_status = ''
  ```

---

#### 14. CSV 解析中异常行被静默丢弃

- **位置**：`core/autoruns_parser.py` 第 285-286 行、第 330-331 行
- **现状**：

  ```python
  except Exception:
      continue
  ```

- **问题**：没有记录被跳过的行数或内容。在解析大量条目时，可能有多行被跳过但用户完全无感知。
- **影响**：可能遗漏持久化条目，用户完全无感知。
- **建议**：增加跳过行数的计数和日志记录：

  ```python
  skipped_count = 0
  for row in reader:
      try:
          ...
      except Exception as e:
          skipped_count += 1
          logger.warning(f"跳过异常行: {e}")
          continue
  if skipped_count > 0:
      logger.warning(f"共跳过 {skipped_count} 个异常条目")
  ```

---

#### 15. AutorunEntry 重建时丢失多个字段

- **位置**：`ui/autoruns_tab.py` 第 1113-1130 行
- **现状**：重建 `AutorunEntry` 时未传递 `file_exists`、`md5`、`sha256` 字段
- **问题**：
  - `file_exists` 默认值为 `True`，如果原始条目文件不存在，重建后错误地认为文件存在 — **影响严重**
  - `md5`、`sha256` 默认值为空字符串 `""`，重建后哈希信息丢失 — 影响较小
- **影响**：`file_exists` 影响风险等级判断，错误的值可能误导分析人员。
- **建议**：重建时传递所有缺失字段：

  ```python
  entry = AutorunEntry(
      ...
      md5=entry_data.get('md5', ''),
      sha256=entry_data.get('sha256', ''),
      file_exists=entry_data.get('file_exists', True),
  )
  ```

---

#### 16. UTF-16LE 解码使用 errors='ignore' 可能截断数据

- **位置**：`core/autoruns_parser.py` 第 169 行
- **现状**：

  ```python
  csv_text = stdout_bytes.decode('utf-16le', errors='ignore')
  ```

- **问题**：`errors='ignore'` 会静默丢弃无法解码的字节。某些条目名称或路径中的非 ASCII 字符被截断，可能导致路径不完整。
- **影响**：文件路径不完整可能导致"文件不存在"的误判，以及无法正确定位恶意文件。
- **建议**：使用 `errors='replace'` 替代，至少保留占位符标记被截断的位置：

  ```python
  csv_text = stdout_bytes.decode('utf-16le', errors='replace')
  ```

---

## 四、跨模块共性问题

### 🔴 严重

#### 17. DataStore 无持久化机制 — 程序退出数据全部丢失

- **位置**：`core/data_store.py`
- **现状**：所有数据仅存内存，`_autoruns_entries`、`_network_connections_current`、`_sysmon_events` 均为 Python 列表
- **问题**：程序崩溃或关闭后，所有采集数据丢失。在应急响应场景下，数据丢失是严重问题。
- **影响**：
  1. 攻击者可能通过触发崩溃来销毁证据
  2. 长时间采集后意外退出导致所有工作白费
  3. 无法进行事后复盘分析
- **建议**：实现自动持久化机制：
  - 使用 SQLite 数据库存储事件数据
  - 采集过程中定期写入磁盘（如每 100 条事件或每 30 秒）
  - 启动时检查是否有未完成的数据，提供恢复选项

---

### 🟡 中等

#### 18. 网络监控和 Sysmon 数据不关联

- **现状**：
  - 网络监控使用 `psutil` 获取实时连接（`NetworkConnection`）
  - Sysmon 通过事件日志获取连接（`NetworkConnectEvent`）
  - 两者使用完全不同的数据模型，没有关联机制
- **问题**：无法将实时连接与历史事件关联分析。例如，发现一个可疑实时连接，无法快速查看该 IP/端口的历史 Sysmon 事件。
- **影响**：降低应急响应效率，分析人员需要手动在两个模块间切换查找。
- **建议**：在 DataStore 中建立关联索引，基于 `(PID, destination_ip, destination_port)` 等维度关联两个模块的数据。

---

#### 19. 时间戳格式不统一

- **现状**：
  - `NetworkMonitor`：`"%Y/%m/%d %H:%M:%S"`（本地时间）
  - `SysmonEvent`：`"%Y/%m/%d %H:%M:%S"`（UTC 时间，但显示格式相同）
  - `AutorunEntry`：原始时间字符串（格式不确定，取决于 autorunsc 输出）
- **问题**：三个模块的时间戳格式和时区不统一，跨模块时间线分析时可能产生混淆。
- **建议**：统一时间戳格式和时区：
  - **时区策略**：全部统一使用本机时间（如北京时间 UTC+8）
  - **格式策略**：保持 `"%Y/%m/%d %H:%M:%S"` 格式不变（因全部统一为本机时间，无需在字符串中标注时区）
  - **Sysmon 修复**：`_parse_timestamp` 中将 `dt.astimezone(timezone.utc)` 改为 `dt.astimezone()`（转本机时间）
  - **AutorunEntry**：如 autorunsc 输出时间格式不统一，在解析时统一格式化

---

## 五、问题严重性汇总

| 编号 | 模块 | 严重性 | 问题简述 |
|------|------|--------|----------|
| #1 | 网络监控 | 🔴 严重 | 连接时间戳是"刷新时刻"而非"建立时刻" |
| #2 | 网络监控 | 🟡 中等 | PID 复用导致进程信息错乱 |
| #3 | 网络监控 | 🟡 中等 | 过滤 PID=None 的连接可能遗漏线索 |
| #4 | 日志采集 | 🔴 严重 | 事件解析失败时静默丢弃 |
| #5 | 日志采集 | 🔴 严重 | 时间戳解析失败回退为 datetime.now()（两处） |
| #6 | 日志采集 | 🔴 严重 | 事件去重键精度不足 |
| #7 | 日志采集 | 🔴 严重 | Sysmon UTC 与网络监控本地时间不一致 |
| #8 | 日志采集 | 🟡 中等 | 超过 50000 条事件时旧事件永久丢失 |
| #9 | 日志采集 | 🟡 中等 | DataStore 中 Sysmon 事件无去重 |
| #10 | 日志采集 | 🟡 中等 | FileCreateEvent 统一显示为"DLL创建" |
| #11 | 持久化检测 | 🔴 严重 | 服务名称提取逻辑可能导致删除失败 |
| #12 | 持久化检测 | 🟡 中等 | publisher 和 company 映射到同一列 |
| #13 | 持久化检测 | 🟡 中等 | signer 和 signer_status 映射混乱 |
| #14 | 持久化检测 | 🟡 中等 | CSV 解析异常行静默丢弃 |
| #15 | 持久化检测 | 🟡 中等 | AutorunEntry 重建丢失多个字段 |
| #16 | 持久化检测 | 🟡 中等 | UTF-16LE 解码 errors='ignore' 截断数据 |
| #17 | 跨模块 | 🔴 严重 | DataStore 无持久化机制 |
| #18 | 跨模块 | 🟡 中等 | 网络监控和 Sysmon 数据不关联 |
| #19 | 跨模块 | 🟡 中等 | 时间戳格式不统一 |

**统计**：

| 严重性 | 数量 | 问题编号 |
|--------|------|----------|
| 🔴 严重 | 7 | #1, #4, #5, #6, #7, #11, #17 |
| 🟡 中等 | 12 | #2, #3, #8, #9, #10, #12, #13, #14, #15, #16, #18, #19 |

---

## 六、优先修复建议

### P0 — 立即修复（直接影响数据准确性/完整性）

| 优先级 | 问题 | 修复方案 | 预计影响 |
|--------|------|----------|----------|
| P0-1 | #7 时区不一致 | Sysmon `_parse_timestamp` 转本机时间而非 UTC | 修复跨模块时间线偏差 |
| P0-2 | #4 解析失败静默丢弃 | 至少保留 raw_data 并记录日志 | 防止关键事件丢失 |
| P0-3 | #5 时间戳回退为 now() | 两处均改为 epoch=0，UI 标注"时间未知" | 防止错误时间戳污染数据 |
| P0-4 | #11 服务名提取错误 | 从 launch_string 提取真实服务名，删除前验证 | 防止服务删除失败 |

### P1 — 尽快修复（影响数据完整性）

| 优先级 | 问题 | 修复方案 | 预计影响 |
|--------|------|----------|----------|
| P1-1 | #1 连接时间戳语义 | 引入 first_seen_epoch / last_seen_epoch 双时间戳 | 修复时间线准确性，同时为历史清理提供正确依据 |
| P1-2 | #6 去重键精度不足 | 增加事件特征维度（域名/IP/端口等） | 防止高频事件被错误去重 |
| P1-3 | #13 signer 字段拆分 | 从 Signer 列中正确提取签名者和状态 | 修复签名信息丢失 |
| P1-4 | #17 DataStore 持久化 | 增加 SQLite 自动落盘 | 防止崩溃导致数据丢失 |

### P2 — 计划修复（改善数据质量）

| 优先级 | 问题 | 修复方案 | 预计影响 |
|--------|------|----------|----------|
| P2-1 | #15 重建丢失字段 | 传递 file_exists/md5/sha256 字段 | 修复风险等级判断 |
| P2-2 | #8 事件截断 | 实现磁盘溢出机制 | 防止早期事件丢失 |
| P2-3 | #14 异常行静默丢弃 | 增加跳过计数和日志 | 提高数据可审计性 |
| P2-4 | #16 解码截断 | errors='replace' 替代 errors='ignore' | 防止路径截断 |
| P2-5 | #2 PID 复用 | 缓存中存储 create_time 校验 | 防止进程信息错乱 |
| P2-6 | #3 PID=None 过滤 | 保留并标记为"[无进程]" | 防止遗漏可疑连接 |
| P2-7 | #9 DataStore 去重 | add_sysmon_event 增加去重 | 防止重复数据 |
| P2-8 | #10 FileCreateEvent 类型 | 根据后缀动态判断 | 修复类型误标 |
| P2-9 | #12 publisher 映射 | 保持 Company 映射，注释说明同义 | 明确字段语义 |
| P2-10 | #18 跨模块关联 | 建立关联索引 | 提升分析效率 |
| P2-11 | #19 时间戳统一 | 全部使用本机时间 + 统一格式 | 提升跨模块一致性 |

---

## 修订记录

| 日期 | 修订内容 |
|------|----------|
| 2026-05-26 | 初版 |
| 2026-05-26 | 经源码交叉验证后修正：移除原 #2（历史连接永不过期，经验证不成立）、移除原 #5（UDP remote_port 显示不一致，经验证 Python 中整数 0 为 falsy，显示逻辑正确）；补充原 #7 中 `_parse_system_data` 第 71 行的 `datetime.now()` 默认值；修正原 #14 建议（autorunsc CSV 无 Publisher 列）；补充原 #17 中 md5/sha256 丢失字段；修正原 #13 风险描述（主要是删除失败而非误删）；修正严重性分类（#17 DataStore 持久化由 🟢 提升为 🔴，#19 时间戳统一由 🟢 提升为 🟡）；更新时间戳策略为统一本机时间；引入 first_seen_epoch / last_seen_epoch 双时间戳建议 |
