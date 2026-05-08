# opencode_skills

## Skills

### dp-mst-dpcd-parser

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

#### 使用 Demo

**基本用法**：

```bash
# 从标准输入读取日志
dmesg | grep "AUX ->" | python3 scripts/parse_dpcd_log.py

# 从文件读取
python3 scripts/parse_dpcd_log.py dpcd_log.txt

# 使用 hex dump 格式解析
dd if=/dev/drm_dp_aux1 bs=1 skip=$((0x00200)) count=64 status=none \
  | od -tx1 | python3 scripts/parse_dpcd_log.py --format=hex_dump --base-addr=0x00200
```

**示例输入**：

```
27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
27e40000.dp: 0x01410 AUX -> (ret=  7) 0f 07 00 e2 00 6a e3 05
```

**示例输出**：

```
============================================================
LOG SUMMARY
============================================================
Total entries: 3
  ESI accesses: 1
  MST sideband messages: 2
  Reads: 3, Writes: 0

============================================================
KEY FINDINGS
============================================================
CRC errors: 1
  pkt1: body CRC8 mismatch

============================================================
DPCD REGISTER ACCESSES
============================================================
27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
0x02003 (DEVICE_SERVICE_IRQ_VECTOR_ESI0): 0x30
    -bit[5] UP_REQ_MSG_RDY: 1 (read UP_REQ_MSG)
    -bit[4] DOWN_REP_MSG_RDY: 1 (read DOWN_REP_MSG)

============================================================
MST SIDEBAND MESSAGES
============================================================
=== DOWN_REP (0x01400) -> Source reads [Reply] ===
Multi-packet message: 1 packets
  Packet 1/1 (MIDDLE):
    Header: LCT=1 LCR=0 RAD=[] BC=0 Path=0 BodyLen=33 SMT=0 EMT=0 MSN=0 CRC4=0xe
  Reply: ACK, Request: GET_MESSAGE_TRANSACTION_VERSION (0x00)
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
