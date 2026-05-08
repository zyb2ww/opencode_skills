---
name: dp-dpcd-parser
description: Parse DisplayPort MST DPCD and Sideband Message logs from kernel drm subsystem. Use this skill whenever the user provides kernel log output containing AUX transactions, DPCD reads/writes, or MST sideband messages (look for patterns like "drm_dp_dpcd_read", "drm_dp_dpcd_write", "AUX ->", "AUX <-"). This skill handles both single-packet and multi-packet MST message transactions.
---

# DP MST DPCD Log Parser

## Quick Start

Run the parsing script to get structured output, then analyze the results:

```bash
python3 <skill_dir>/scripts/parse_dpcd_log.py <log_file_or_stdin>
```

Options:
- `--format {auto,drm_dp_dump,rockchip,hex_dump}` - Input log format (default: auto-detect)
- `--base-addr 0xAAAAA` - Base DPCD address for hex_dump format (default: 0x00000)
- `--grouped` - Use legacy grouped output format (default: sequential per-entry output)

The script automatically handles:
- Auto-detection of input log format (3 formats supported)
- Log line extraction (regex matching of `0xAAAAA AUX ->/<- (ret= N) HEX_DATA`)
- AUX error code decoding (negative ret values → errno macro + description)
- Address classification (DPCD registers, ESI, MST sideband buffers)
- DPCD register bit-field decoding (using `scripts/dpcd_regs.json`)
- Multi-offset AUX read concatenation (e.g., 0x1400 + 0x1410 = one message)
- Sideband MSG header parsing (LCT/LCR/SMT/EMT/MSN/BodyLen)
- CRC-4 header validation (polynomial x^4+x+1, per DP spec)
- CRC-8 body validation (polynomial 0xD5, per DP spec)
- Multi-packet message assembly (SMT=1,EMT=0 -> SMT=0,EMT=0 -> SMT=0,EMT=1)
- Bit-level MT detail parsing via BitReader (all 14 MT types + NAK)
- Request/Reply auto-pairing (by MSN + Request_ID)
- MST topology tree auto-generation (from LINK_ADDRESS replies)
- Key Findings auto-summary (topology, NAK, CRC errors, AUX errors)

## Supported Log Formats

### 1. drm_dp_dump_access (Kernel Standard)

From `drivers/gpu/drm/display/drm_dp_helper.c`:

```
<device>: 0x<addr> AUX -> (ret= 16) XX XX XX ...   # Normal (ret > 0, with data)
<device>: 0x<addr> AUX -> (ret=-110)                # Error (ret < 0, no data)
```

With dmesg prefix:
```
[  123.456789] [drm:dp] 27e40000.dp: 0x02003 AUX -> (ret= 16) 01 00
[  123.456789] 27e40000.dp: 0x02003 AUX -> (ret=-110)
```

### 2. Hex Dump (dd + od)

Read DPCD registers via `/dev/drm_dp_auxN`:

```bash
dd if=/dev/drm_dp_aux1 bs=1 skip=$((0x00200)) count=64 status=none \
  | od -tx1 | python3 parse_dpcd_log.py --format=hex_dump --base-addr=0x00200
```

Or save to file first:
```bash
dd if=/dev/drm_dp_aux1 bs=1 skip=$((0x00200)) count=64 status=none | od -tx1 > dump.txt
python3 parse_dpcd_log.py --format=hex_dump --base-addr=0x00200 dump.txt
```

### 3. Rockchip Format

```
[  timestamp] device.dp: 0xAAAAA AUX -> (ret= N) XX XX
```

## AUX Error Codes

| ret | Macro | Description |
|:----|:------|:------------|
| -5 | EIO | I/O error (AUX NACK/DEFER after retries) |
| -11 | EAGAIN | Try again (temporarily unavailable) |
| -16 | EBUSY | Device or resource busy (AUX powered down) |
| -22 | EINVAL | Invalid argument |
| -32 | EPIPE | Broken pipe |
| -71 | EPROTO | Protocol error (short reply) |
| -110 | ETIMEDOUT | Connection timed out (AUX timeout) |
| -121 | EREMOTEIO | Remote I/O error (I2C-over-AUX failure) |

## When to Use the Script vs. Manual Analysis

**Use the script** for: All DPCD register decoding, MST message extraction, multi-packet assembly, all 14 MT type detail parsing, CRC validation, topology tree generation, request/reply pairing, error detection.

**Manual analysis needed for**: EDID decoding, root-causing NAK reasons, cross-referencing with hardware behavior.

## Output Requirements

**IMPORTANT**: When running the script, **always include the complete parsed output** in your response:
1. Copy the **full script output** (LOG SUMMARY, KEY FINDINGS, and SEQUENTIAL LOG ENTRIES sections)
2. Do NOT summarize or truncate the detailed register/MST decoding
3. After presenting the full output, provide a concise analysis summary highlighting key findings
4. If the output is very long, you may omit repetitive entries but must include at least one complete example of each access type (DPCD read/write, MST message, ESI, etc.)

## Demo Example

### Input Log (drm_dp_dump format)
```
[  123.456] 27e40000.dp: 0x02003 AUX -> (ret= 16) 30 00
[  123.457] 27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
[  123.460] 27e40000.dp: 0x01410 AUX -> (ret=  7) 0f 07 00 e2 00 6a e3
```

### Script Output (with detailed decoding)
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
MST messages parsed: 1
  DOWN_REP ACK ? (2 pkt)

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

### Analysis Summary
- **ESI 中断**: 0x02003=0x30, bit[5]=1 (UP_REQ_MSG_RDY), bit[4]=1 (DOWN_REP_MSG_RDY)
- **MST 消息**: DOWN_REP buffer 读取，但 SMT/EMT 组合不合法 (0/0=MIDDLE)，缺少 START packet
- **CRC 错误**: Body CRC8 校验失败，数据不完整
- **根因**: Source 轮询 ESI 不及时，DOWN_REP buffer 被覆盖导致 START packet 丢失

## Output Format

The script outputs 3 sections by default (sequential mode):

### 1. LOG SUMMARY
- Total entries, breakdown by type, time span
- Paired request/reply messages

### 2. KEY FINDINGS
- MST topology tree (auto-generated from LINK_ADDRESS replies)
- NAK messages (with reason codes)
- CRC errors (header CRC4 / body CRC8 mismatches)
- AUX errors (timeouts, I/O errors)

### 3. SEQUENTIAL LOG ENTRIES (default)
Each DPCD log line is output in original order with:
- **Original log line** preserved verbatim
- **Register decoding** for DPCD/ESI/LTTPR addresses (bit-field level)
- **MST sideband message parsing** at first AUX read of each message:
  - Sideband header (LCT/LCR/RAD/SMT/EMT/MSN/BodyLen/CRC4)
  - Body data and CRC-8
  - Assembled Message Transaction layer data
  - Request/Reply type and name
  - Detailed MT field parsing (all 14 types + NAK)
  - Paired request/reply annotation
- **Continuation notes** for subsequent AUX reads of the same MST message

### Grouped Mode (--grouped)
Use `--grouped` flag for the legacy output format with separate DPCD register and MST message sections.

## Address Classification Quick Reference

| Address Range | Type | Description |
|:-------------|:-----|:------------|
| 0x00000-0x00FFF | DPCD Register | Standard capability/status registers |
| 0x01000-0x011FF | DOWN_REQ | MST Downstream Request (Source writes) |
| 0x01200-0x013FF | UP_REP | MST Upstream Reply (Source writes) |
| 0x01400-0x015FF | DOWN_REP | MST Downstream Reply (Source reads) |
| 0x01600-0x017FF | UP_REQ | MST Upstream Request (Source reads) |
| 0x02000-0x021FF | ESI | Event Status Indicator |

## Sideband MSG Header (3-7 bytes)

```
Byte 0: [7:4] LCT  [3:0] LCR
Byte 1+: RAD nibbles (LCT-1 of them)
Last 2 bytes before body:
  [-2]: [7] Broadcast [6] Path [5:0] Body_Length
  [-1]: [7] SMT [6] EMT [5] zero [4] MSN [3:0] CRC4
```

**SMT/EMT combinations**: 1/1=single, 1/0=start, 0/0=middle, 0/1=end

## Request Identifiers

| ID | Name | Direction |
|:---|:-----|:----------|
| 0x01 | LINK_ADDRESS | DOWN |
| 0x02 | CONNECTION_STATUS_NOTIFY | UP |
| 0x10 | ENUM_PATH_RESOURCES | DOWN |
| 0x11 | ALLOCATE_PAYLOAD | DOWN |
| 0x14 | CLEAR_PAYLOAD_ID_TABLE | DOWN |
| 0x20 | REMOTE_DPCD_READ | DOWN |
| 0x22 | REMOTE_I2C_READ | DOWN |
| 0x21 | REMOTE_DPCD_WRITE | DOWN |
| 0x23 | REMOTE_I2C_WRITE | DOWN |

Full list (16 types) in `references/mst_sideband_spec.md`.

## ESI IRQ Bits (0x02003)

Key bits for MST: bit[4]=DOWN_REP_MSG_RDY, bit[5]=UP_REQ_MSG_RDY.
When Source polls ESI and sees bit[4]=1, it reads DOWN_REP buffer, then W1C clears bit[4].

## Reference Files

**Core:**
- `scripts/dpcd_regs.json` - DPCD register definitions (address-indexed, bit-field level)
- `scripts/parse_dpcd_log.py` - Automated parsing script

**Reference (split into separate files):**
- `references/dpcd_registers.md` - DPCD address space + register tables (384 lines, 15 sections)
- `references/mst_sideband_spec.md` - Sideband MSG format + 14 MT types + CRC (779 lines, 37 sections)
- `references/parsing_examples.md` - Parsing examples + quick ref tables (450 lines, 13 sections)

## Notes

- The script uses 3ms gap threshold to group consecutive AUX reads into message reads
- Multi-packet assembly tracks SMT/EMT flags across poll cycles
- DPCD_REV major_revision: register stores the digit directly (1=r1.0, 2=r1.1, etc.)
- BitReader class handles bit-level MT field parsing, eliminating byte-alignment errors in LINK_ADDRESS and other multi-bit-field message types
- Request/Reply pairing matches DOWN_REQ→DOWN_REP and UP_REQ→UP_REP by Request_ID
- CRC-4 uses polynomial x^4+x+1 with bit-level shift register (not the kernel's nibble-based approach)
- CRC-8 uses polynomial 0xD5 (x^8+x^7+x^5+x^4+x^2+1) with lookup table
