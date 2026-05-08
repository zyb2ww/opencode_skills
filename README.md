# opencode_skills

## Skills

### dp-dpcd-parser

**DisplayPort MST DPCD 和 Sideband Message 日志解析工具**

#### 作用

该 skill 用于解析 Linux 内核 DRM 子系统输出的 DisplayPort MST DPCD 和 Sideband Message 日志。它能够：

- 自动识别 3 种日志格式（drm_dp_dump_access、Rockchip 格式、Hex Dump）
- 解码 DPCD 寄存器位字段（使用 `dpcd_regs.json` 数据库）
- 解析 MST Sideband 消息头（LCT/LCR/RAD/SMT/EMT/MSN/BodyLen/CRC4）
- 验证 CRC-4 头校验和 CRC-8 体校验
- 组装多包消息（SMT/EMT 标志跟踪）
- 解析所有 14 种 Message Transaction 类型及 NAK
- 自动生成 MST 拓扑树（从 LINK_ADDRESS 回复）
- 请求/回复自动配对
- 关键发现自动汇总（拓扑、NAK、CRC 错误、AUX 错误）

#### 使用场景

- **驱动开发调试**：分析 DP MST 驱动日志，快速定位 AUX 通信问题
- **硬件故障排查**：识别 CRC 校验错误、AUX 超时、NAK 错误码
- **协议分析**：解析 MST Sideband 消息事务，理解设备间通信流程
- **EDID 读取调试**：跟踪 REMOTE_I2C_READ 多包消息，验证 EDID 数据完整性
- **拓扑发现**：从 LINK_ADDRESS 消息自动生成 MST 拓扑树

#### 在 opencode 中使用

该 skill 已注册为 opencode 的自动触发 skill。当用户在对话中粘贴或提供包含以下特征的内核日志时，skill 会自动激活：

- 包含 `AUX ->` / `AUX <-` 模式的 dmesg 输出
- 包含 `drm_dp_dpcd_read` / `drm_dp_dpcd_write` 的内核日志
- 包含 DPCD 地址（如 `0x02003`、`0x01400`）和十六进制数据的日志行
- 用户明确提到"DPCD"、"MST sideband"、"AUX 日志解析"等关键词

**触发方式**：

1. **直接粘贴日志**：在 opencode 对话中粘贴内核日志，skill 会自动识别并调用解析脚本
2. **提供日志文件路径**：告诉 opencode 日志文件路径（如 `解析这个文件 dpcd_log.txt`）
3. **提问式触发**：提出与 DPCD/MST 日志分析相关的问题（如 `帮我分析这段 AUX 日志`、`这个 MST sideband 消息是什么意思`）

**opencode 会自动**：
- 识别日志格式并调用 `parse_dpcd_log.py` 脚本
- 将解析结果整理为人类可读的格式
- 对关键发现（CRC 错误、NAK、拓扑结构）给出解释和调试建议

#### 使用 Demo

**Demo 1：在 opencode 中粘贴日志，自动触发解析**

用户输入：
```
帮我分析这段 dmesg 日志，看看 MST 有什么问题：

[  123.456] 27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
[  123.457] 27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
[  123.460] 27e40000.dp: 0x01410 AUX -> (ret=  7) 0f 07 00 e2 00 6a e3
```

opencode 自动触发 skill，调用脚本后输出完整解析结果：
```
============================================================
LOG SUMMARY
============================================================
Total entries: 3
  DPCD register accesses: 0
  ESI accesses: 1
  MST sideband messages: 2
  Reads: 3, Writes: 0
  Time span: 123.456000s - 123.460000s

============================================================
KEY FINDINGS
============================================================
CRC errors: 1
  pkt1: body CRC8 mismatch

============================================================
SEQUENTIAL LOG ENTRIES (per-entry with decoding)
============================================================
  [  123.456] 27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
  0x02003 (DEVICE_SERVICE_IRQ_VECTOR_ESI0): 0x30
      -bit[6] SINK_SPECIFIC_IRQ: 0
      -bit[5] UP_REQ_MSG_RDY: 1 (read UP_REQ_MSG)
      -bit[4] DOWN_REP_MSG_RDY: 1 (read DOWN_REP_MSG)
      -bit[3] MCCS_IRQ: 0
      -bit[2] CP_IRQ: 0
      -bit[1] AUTOMATED_TEST_REQUEST: 0
      -bit[0] RESERVED: 0
  0x02004 (DEVICE_SERVICE_IRQ_VECTOR_ESI1): 0x00
      -bit[2] CEC_IRQ: 0
      -bit[1] LOCK_ACQUISITION_REQUEST: 0
      -bit[0] RX_GTC_PRIMARY_REQ_STATUS_CHANGE: 0

  [  123.457] 27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
  Packet 1/2 (MIDDLE):
    Header: LCT=1 LCR=0 RAD=[] BC=0 Path=0 BodyLen=33 SMT=0 EMT=0 MSN=0 CRC4=0xe [BODY_CRC8_FAIL]
    Body data: 00 6d d8 5d c4 01 78 80 70 00 30 f0 00

  [  123.460] 27e40000.dp: 0x01410 AUX -> (ret=  7) 0f 07 00 e2 00 6a e3
  Packet 2/2 (MIDDLE):
    Header: LCT=0 LCR=0 RAD=[] BC=0 Path=0 BodyLen=0 SMT=0 EMT=0 MSN=0 CRC4=0x0
  ── MST Sideband Message (DOWN_REP 0x01400) ──
  DOWN_REP (0x01400) -> Source reads [Reply]
  Multi-packet message: 2 packets
  Packet 1/2 (MIDDLE):
    Header (byte positions):
      Byte 0 [7:4] LCT=1, [3:0] LCR=0
      Byte 1..N-2 [(none)] RAD=[]
      Byte N-2 [7] BC=0 [6] Path=0 [5:0] BodyLen=33
      Byte N-1 [7] SMT=0 [6] EMT=0 [4] MSN=0 [3:0] CRC4=0xe [BODY_CRC8_FAIL]
    Body data: 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
  Packet 2/2 (MIDDLE):
    Header (byte positions):
      Byte 0 [7:4] LCT=0, [3:0] LCR=0
      Byte 1..N-2 [(none)] RAD=[]
      Byte N-2 [7] BC=0 [6] Path=0 [5:0] BodyLen=0
      Byte N-1 [7] SMT=0 [6] EMT=0 [4] MSN=0 [3:0] CRC4=0x0
  Assembled MT (13 bytes):
    00 6d d8 5d c4 01 78 80 70 00 30 f0 00
  MT Byte[0]: [7] reply=0 (ACK), [6:0] request_id=0x00 (GET_MESSAGE_TRANSACTION_VERSION)
  Reply: ACK, Request: GET_MESSAGE_TRANSACTION_VERSION (0x00)
    GET_MESSAGE_TRANSACTION_VERSION ACK detail:
      Version[Byte[0]7:0]: 0x00 (unknown)
```

**分析总结**：
- **ESI 中断**: 0x02003=0x30，bit[5]=1 (UP_REQ_MSG_RDY), bit[4]=1 (DOWN_REP_MSG_RDY)
- **MST 消息**: DOWN_REP buffer 读取，但 SMT/EMT 组合不合法 (0/0=MIDDLE)，缺少 START packet
- **CRC 错误**: Body CRC8 校验失败，数据不完整
- **根因**: Source 轮询 ESI 不及时，DOWN_REP buffer 被覆盖导致 START packet 丢失
- **建议**: 检查 ESI 轮询间隔，确认驱动在收到 DOWN_REP_MSG_RDY 后立即读取完整缓冲区
```
帮我分析这段 dmesg 日志，看看 MST 有什么问题：

[  123.456] 27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
[  123.457] 27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
[  123.460] 27e40000.dp: 0x01410 AUX -> (ret=  7) 0f 07 00 e2 00 6a e3 05
```

opencode 自动触发 skill，调用脚本后输出：
```
解析结果：

=== LOG SUMMARY ===
- 共 3 条日志：1 条 ESI 访问，2 条 MST sideband 消息
- 全部为读操作

=== KEY FINDINGS ===
⚠ CRC 错误：1 处
  - pkt1: body CRC8 mismatch（数据可能在传输中被破坏）

=== ESI 寄存器 ===
0x02003 (DEVICE_SERVICE_IRQ_VECTOR_ESI0) = 0x30
  - bit[5] UP_REQ_MSG_RDY = 1 → 有上行请求消息待处理
  - bit[4] DOWN_REP_MSG_RDY = 1 → 有下行回复消息待处理

=== MST SIDEBAND 消息 ===
DOWN_REP (0x01400)：Source 读取的 Reply
  - 单包消息，Header: LCT=1 LCR=0 SMT=0 EMT=0 MSN=0 CRC4=0xe
  - Reply: ACK，请求类型: GET_MESSAGE_TRANSACTION_VERSION

调试建议：CRC8 校验失败说明这条 sideband 消息在传输过程中可能出现了位错误，
建议检查 DP 线缆连接和 AUX 通道信号完整性。
```

**Demo 2：提供日志文件路径**

用户输入：
```
解析文件 /tmp/dpcd_dump.txt 中的 DPCD 日志
```

opencode 自动调用：
```bash
python3 <skill_dir>/scripts/parse_dpcd_log.py /tmp/dpcd_dump.txt
```

然后基于输出进行解读和提供建议。

**Demo 3：直接使用命令行脚本**

```bash
# 从标准输入读取日志
dmesg | grep "AUX ->" | python3 scripts/parse_dpcd_log.py

# 从文件读取
python3 scripts/parse_dpcd_log.py dpcd_log.txt

# 使用 hex dump 格式解析
dd if=/dev/drm_dp_aux1 bs=1 skip=$((0x00200)) count=64 status=none \
  | od -tx1 | python3 scripts/parse_dpcd_log.py --format=hex_dump --base-addr=0x00200
```

#### 命令行选项

- `--format {auto,drm_dp_dump,rockchip,hex_dump}` - 输入日志格式（默认：自动检测）
- `--base-addr 0xAAAAA` - Hex Dump 格式的基地址（默认：0x00000）
- `--grouped` - 使用分组的输出格式（默认：顺序输出）

#### 支持的文件

- `scripts/parse_dpcd_log.py` - 主解析脚本
- `scripts/dpcd_regs.json` - DPCD 寄存器定义数据库
- `references/dpcd_registers.md` - DPCD 地址空间和寄存器详解
- `references/mst_sideband_spec.md` - MST Sideband 消息格式和 14 种 MT 类型
- `references/parsing_examples.md` - 解析示例和快速参考表
