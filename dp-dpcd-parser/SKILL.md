---
name: dp-mst-dpcd-parser
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
