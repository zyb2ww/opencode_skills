#!/usr/bin/env python3
"""Parse DisplayPort MST DPCD and Sideband Message logs from kernel drm subsystem."""

import json
import re
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

REQUEST_IDS = {
    0x00: "GET_MESSAGE_TRANSACTION_VERSION",
    0x01: "LINK_ADDRESS",
    0x02: "CONNECTION_STATUS_NOTIFY",
    0x10: "ENUM_PATH_RESOURCES",
    0x11: "ALLOCATE_PAYLOAD",
    0x12: "QUERY_PAYLOAD",
    0x13: "RESOURCE_STATUS_NOTIFY",
    0x14: "CLEAR_PAYLOAD_ID_TABLE",
    0x20: "REMOTE_DPCD_READ",
    0x21: "REMOTE_DPCD_WRITE",
    0x22: "REMOTE_I2C_READ",
    0x23: "REMOTE_I2C_WRITE",
    0x24: "POWER_UP_PHY",
    0x25: "POWER_DOWN_PHY",
    0x30: "SINK_EVENT_NOTIFY",
    0x38: "QUERY_STREAM_ENC_STATUS",
}

NAK_REASONS = {
    0x01: "WRITE_FAILURE",
    0x02: "INVALID_RAD",
    0x03: "CRC_FAILURE",
    0x04: "BAD_PARAM",
    0x05: "DEFER",
    0x06: "LINK_FAILURE",
    0x07: "NO_RESOURCES",
    0x08: "DPCD_FAIL",
    0x09: "I2C_NAK",
    0x0A: "ALLOCATE_FAIL",
}

PEER_DEVICE_TYPES = {
    0: "No device",
    1: "MST Source / SST-only Source Branch",
    2: "MST Branch / SST-only Branch",
    3: "SST Sink (no Branching Unit)",
    4: "DP-to-Legacy converter (VGA/DVI/HDMI)",
    5: "DP-to-Wireless converter",
    6: "Wireless-to-DP converter",
}

AUX_ERRORS = {
    -1: ("EPERM", "Operation not permitted"),
    -2: ("ENOENT", "No such file or directory"),
    -5: ("EIO", "I/O error"),
    -6: ("ENXIO", "No such device or address"),
    -9: ("EBADF", "Bad file number"),
    -11: ("EAGAIN", "Try again"),
    -12: ("ENOMEM", "Out of memory"),
    -14: ("EFAULT", "Bad address"),
    -16: ("EBUSY", "Device or resource busy"),
    -19: ("ENODEV", "No such device"),
    -22: ("EINVAL", "Invalid argument"),
    -28: ("ENOSPC", "No space left on device"),
    -32: ("EPIPE", "Broken pipe"),
    -34: ("ERANGE", "Math result not representable"),
    -71: ("EPROTO", "Protocol error"),
    -110: ("ETIMEDOUT", "Connection timed out"),
    -121: ("EREMOTEIO", "Remote I/O error"),
}

BUFFER_NAMES = {
    (0x01000, 0x011FF): "DOWN_REQ",
    (0x01200, 0x013FF): "UP_REP",
    (0x01400, 0x015FF): "DOWN_REP",
    (0x01600, 0x017FF): "UP_REQ",
}

MST_BUFFER_TYPES = set(BUFFER_NAMES.values())

LINE_PATTERN = re.compile(
    r'0x([0-9a-fA-F]{5})\s+AUX\s+(->|<-)\s+\(ret=\s*(\d+)\)\s+((?:[0-9a-fA-F]{2}\s*)+)'
)

DRM_DP_DUMP_PATTERN = re.compile(
    r'(?:\[\s*[\d.]+\]\s+)?'
    r'(?:\[drm:[\w]+\]\s+)?'
    r'(\S+):\s+'
    r'0x([0-9a-fA-F]{1,5})\s+'
    r'AUX\s+(->|<-)\s+'
    r'\(ret=\s*(-?\d+)\)'
    r'(?:\s+((?:[0-9a-fA-F]{2}\s*)+))?'
)

HEX_DUMP_LINE_PATTERN = re.compile(
    r'^([0-7]+)\s+((?:[0-9a-fA-F]{2}\s*)+)\s*$'
)


class BitReader:
    def __init__(self, data):
        self.data = data
        self.bit_pos = 0

    def read_bits(self, n):
        if n <= 0:
            return 0
        val = 0
        for _ in range(n):
            byte_idx = self.bit_pos >> 3
            bit_idx = 7 - (self.bit_pos & 7)
            if byte_idx < len(self.data):
                val = (val << 1) | ((self.data[byte_idx] >> bit_idx) & 1)
            else:
                val = val << 1
            self.bit_pos += 1
        return val

    def read_byte(self):
        return self.read_bits(8)

    def read_bytes(self, n):
        return [self.read_byte() for _ in range(n)]

    def remaining_bits(self):
        return len(self.data) * 8 - self.bit_pos

    def align_to_byte(self):
        rem = self.bit_pos & 7
        if rem:
            self.bit_pos += 8 - rem

    def bit_spec(self, start_bit, num_bits):
        """Return a byte/bit position specifier like 'Byte[0:7:4]' for MT data."""
        s_byte = start_bit >> 3
        s_bit = 7 - (start_bit & 7)
        e_bit_pos = start_bit + num_bits - 1
        e_byte = e_bit_pos >> 3
        e_bit = 7 - (e_bit_pos & 7)
        if s_byte == e_byte:
            return f"Byte[{s_byte}]{s_bit}:{e_bit}"
        else:
            return f"Byte[{s_byte}]{s_bit}:Byte[{e_byte}]{e_bit}"


def crc4_check(header_bytes, num_bits):
    """CRC-4 per DP spec: polynomial x^4 + x + 1, init=0, process bits MSB first."""
    crc = 0
    for i in range(num_bits):
        byte_idx = i >> 3
        bit_idx = 7 - (i & 7)
        bit = (header_bytes[byte_idx] >> bit_idx) & 1
        feedback = ((crc >> 3) & 1) ^ bit
        crc = (crc << 1) & 0xF
        if feedback:
            crc ^= 0x3
    return crc


def crc8_check(data_bytes):
    """CRC-8 per DP spec: polynomial x^8 + x^7 + x^5 + x^4 + x^2 + 1 = 0xD5."""
    table = [
        0x00, 0xD5, 0x7F, 0xAA, 0xFE, 0x2B, 0x81, 0x54,
        0x29, 0xFC, 0x56, 0x83, 0xD7, 0x02, 0xA8, 0x7D,
        0x52, 0x87, 0x2D, 0xF8, 0xAC, 0x79, 0xD3, 0x06,
        0x7B, 0xAE, 0x04, 0xD1, 0x85, 0x50, 0xFA, 0x2F,
        0xA4, 0x71, 0xDB, 0x0E, 0x5A, 0x8F, 0x25, 0xF0,
        0x8D, 0x58, 0xF2, 0x27, 0x73, 0xA6, 0x0C, 0xD9,
        0xF6, 0x23, 0x89, 0x5C, 0x08, 0xDD, 0x77, 0xA2,
        0xDF, 0x0A, 0xA0, 0x75, 0x21, 0xF4, 0x5E, 0x8B,
        0x9D, 0x48, 0xE2, 0x37, 0x63, 0xB6, 0x1C, 0xC9,
        0xB4, 0x61, 0xCB, 0x1E, 0x4A, 0x9F, 0x35, 0xE0,
        0xCF, 0x1A, 0xB0, 0x65, 0x31, 0xE4, 0x4E, 0x9B,
        0xE6, 0x33, 0x99, 0x4C, 0x18, 0xCD, 0x67, 0xB2,
        0x39, 0xEC, 0x46, 0x93, 0xC7, 0x12, 0xB8, 0x6D,
        0x10, 0xC5, 0x6F, 0xBA, 0xEE, 0x3B, 0x91, 0x44,
        0x6B, 0xBE, 0x14, 0xC1, 0x95, 0x40, 0xEA, 0x3F,
        0x42, 0x97, 0x3D, 0xE8, 0xBC, 0x69, 0xC3, 0x16,
        0xEF, 0x3A, 0x90, 0x45, 0x11, 0xC4, 0x6E, 0xBB,
        0xC6, 0x13, 0xB9, 0x6C, 0x38, 0xED, 0x47, 0x92,
        0xBD, 0x68, 0xC2, 0x17, 0x43, 0x96, 0x3C, 0xE9,
        0x94, 0x41, 0xEB, 0x3E, 0x6A, 0xBF, 0x15, 0xC0,
        0x4B, 0x9E, 0x34, 0xE1, 0xB5, 0x60, 0xCA, 0x1F,
        0x62, 0xB7, 0x1D, 0xC8, 0x9C, 0x49, 0xE3, 0x36,
        0x19, 0xCC, 0x66, 0xB3, 0xE7, 0x32, 0x98, 0x4D,
        0x30, 0xE5, 0x4F, 0x9A, 0xCE, 0x1B, 0xB1, 0x64,
        0x72, 0xA7, 0x0D, 0xD8, 0x8C, 0x59, 0xF3, 0x26,
        0x5B, 0x8E, 0x24, 0xF1, 0xA5, 0x70, 0xDA, 0x0F,
        0x20, 0xF5, 0x5F, 0x8A, 0xDE, 0x0B, 0xA1, 0x74,
        0x09, 0xDC, 0x76, 0xA3, 0xF7, 0x22, 0x88, 0x5D,
        0xD6, 0x03, 0xA9, 0x7C, 0x28, 0xFD, 0x57, 0x82,
        0xFF, 0x2A, 0x80, 0x55, 0x01, 0xD4, 0x7E, 0xAB,
        0x84, 0x51, 0xFB, 0x2E, 0x7A, 0xAF, 0x05, 0xD0,
        0xAD, 0x78, 0xD2, 0x07, 0x53, 0x86, 0x2C, 0xF9,
    ]
    crc = 0
    for byte_val in data_bytes:
        crc = table[crc ^ byte_val]
    return crc


def verify_sideband_crc(header_bytes, body_data_with_crc, header_len):
    num_bits = header_len * 8 - 4
    header_crc_expected = crc4_check(header_bytes, num_bits)
    header_crc_actual = header_bytes[-1] & 0xF
    body_crc_ok = None
    if body_data_with_crc and len(body_data_with_crc) >= 1:
        body_crc_actual = body_data_with_crc[-1]
        body_crc_expected = crc8_check(body_data_with_crc[:-1])
        body_crc_ok = body_crc_actual == body_crc_expected
    return header_crc_expected == header_crc_actual, body_crc_ok


def classify_address(addr):
    if 0x00000 <= addr <= 0x00FFF:
        return "DPCD_REGISTER"
    for (start, end), name in BUFFER_NAMES.items():
        if start <= addr <= end:
            return name
    if 0x02000 <= addr <= 0x021FF:
        return "ESI"
    if 0x02200 <= addr <= 0x022FF:
        return "EXTENDED_RECEIVER_CAP"
    if 0x02300 <= addr <= 0x023FF:
        return "DEVICE_SPECIFIC_PARAMS"
    if 0x03000 <= addr <= 0x030FF:
        return "PROTOCOL_CONVERTER"
    if 0x03100 <= addr <= 0x031FF:
        return "DSC_ENCODER"
    if 0xF0000 <= addr <= 0xF0FFF:
        return "LTTPR_REPEATER"
    return "UNKNOWN"


def get_buffer_base(addr):
    for (start, end), name in BUFFER_NAMES.items():
        if start <= addr <= end:
            return start, name
    return None, None


def parse_log_lines(text):
    entries = []
    for line in text.strip().splitlines():
        m = LINE_PATTERN.search(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        direction = "read" if m.group(2) == "->" else "write"
        ret_size = int(m.group(3))
        data = [int(b, 16) for b in m.group(4).split()]
        ts_match = re.search(r'\[\s*([\d.]+)\]', line)
        timestamp = float(ts_match.group(1)) if ts_match else None
        dev_match = re.search(r'(\w+\.dp):', line)
        device = dev_match.group(1) if dev_match else None
        func_match = re.search(r'\[drm:(\w+)\]', line)
        func = func_match.group(1) if func_match else None
        entries.append({
            "addr": addr,
            "direction": direction,
            "ret_size": ret_size,
            "data": data,
            "timestamp": timestamp,
            "device": device,
            "func": func,
            "raw_line": line.strip(),
        })
    return entries


def detect_format(text):
    sample_lines = text.strip().splitlines()[:10]
    for line in sample_lines:
        if DRM_DP_DUMP_PATTERN.search(line):
            return "drm_dp_dump"
    for line in sample_lines:
        if HEX_DUMP_LINE_PATTERN.match(line.strip()):
            has_aux = any("AUX" in l for l in sample_lines)
            if not has_aux:
                return "hex_dump"
    for line in sample_lines:
        if LINE_PATTERN.search(line):
            return "rockchip"
    return "unknown"


def _make_entry(addr, direction, ret_size, data, timestamp=None, device=None, func=None, error=None, raw_line=None):
    return {
        "addr": addr,
        "direction": direction,
        "ret_size": ret_size,
        "data": data,
        "timestamp": timestamp,
        "device": device,
        "func": func,
        "error": error,
        "raw_line": raw_line,
    }


def parse_drm_dp_dump_lines(text):
    entries = []
    for line in text.strip().splitlines():
        m = DRM_DP_DUMP_PATTERN.search(line)
        if not m:
            continue
        device = m.group(1)
        addr = int(m.group(2), 16)
        direction = "read" if m.group(3) == "->" else "write"
        ret_size = int(m.group(4))
        hex_str = m.group(5)
        ts_match = re.search(r'\[\s*([\d.]+)\]', line)
        timestamp = float(ts_match.group(1)) if ts_match else None
        error = None
        data = []
        if ret_size < 0:
            err_info = AUX_ERRORS.get(ret_size, (f"UNKNOWN({ret_size})", "Unknown error"))
            error = err_info
        elif ret_size == 0:
            error = ("ZERO_LENGTH", "Zero bytes transferred")
        elif hex_str:
            data = [int(b, 16) for b in hex_str.split()]
        else:
            error = ("MISSING_DATA", "ret>0 but no data in log")
        entries.append(_make_entry(addr, direction, ret_size, data, timestamp, device, error=error, raw_line=line.strip()))
    return entries


def _merge_hex_dump_entries(entries):
    if not entries:
        return entries
    merged = [entries[0].copy()]
    for e in entries[1:]:
        prev = merged[-1]
        prev_end = prev["addr"] + len(prev["data"])
        if e["addr"] == prev_end:
            prev["data"] = prev["data"] + e["data"]
            prev["ret_size"] = len(prev["data"])
        else:
            merged.append(e.copy())
    return merged


def parse_hex_dump(text, base_addr):
    entries = []
    for line in text.strip().splitlines():
        m = HEX_DUMP_LINE_PATTERN.match(line.strip())
        if not m:
            continue
        od_offset = int(m.group(1), 8)
        hex_data = m.group(2)
        if not hex_data.strip():
            continue
        data = [int(b, 16) for b in hex_data.split()]
        addr = base_addr + od_offset
        entries.append(_make_entry(addr, "read", len(data), data, device="hex_dump"))
    return _merge_hex_dump_entries(entries)


def load_regs_db():
    path = os.path.join(SCRIPT_DIR, "dpcd_regs.json")
    with open(path) as f:
        raw = json.load(f)
    db = {}
    for key, val in raw.items():
        addr = int(key, 16)
        db[addr] = val
    return db


def extract_bit_field(byte_val, bits_str):
    high_str, _, low_str = bits_str.partition(":")
    high_parts = [int(x) for x in high_str.split(",")]
    low_parts = [int(x) for x in low_str.split(",")] if low_str else high_parts
    high = max(high_parts)
    low = min(low_parts)
    mask = ((1 << (high - low + 1)) - 1) << low
    return (byte_val & mask) >> low


def decode_register(reg_info, data, base_addr, offset):
    addr = base_addr + offset
    byte_val = data[offset] if offset < len(data) else None
    if byte_val is None:
        return None
    lines = [f"0x{addr:05x} ({reg_info['name']}): 0x{byte_val:02x}"]
    for field in reg_info.get("fields", []):
        val = extract_bit_field(byte_val, field["bits"])
        bits_display = field["bits"]
        name = field["name"]
        line = f"    -bit[{bits_display}] {name}: {val}"
        if "values" in field:
            val_key = f"0x{val:x}" if any(k.startswith("0x") for k in field["values"]) else str(val)
            if val_key in field["values"]:
                line += f" ({field['values'][val_key]})"
            else:
                try:
                    int_key = str(val)
                    if int_key in field["values"]:
                        line += f" ({field['values'][int_key]})"
                except ValueError:
                    pass
        lines.append(line)
    return "\n".join(lines)


def parse_dpcd_registers(entries, regs_db):
    lines = []
    dpcd_entries = [e for e in entries if classify_address(e["addr"]) in (
        "DPCD_REGISTER", "ESI", "EXTENDED_RECEIVER_CAP", "DEVICE_SPECIFIC_PARAMS",
        "PROTOCOL_CONVERTER", "DSC_ENCODER", "LTTPR_REPEATER")]
    grouped = {}
    for e in dpcd_entries:
        key = e["addr"]
        grouped.setdefault(key, []).append(e)
    for addr in sorted(grouped.keys()):
        elist = grouped[addr]
        reg_info = regs_db.get(addr)
        sample = elist[0]
        dev_str = f"{sample['device']}: " if sample["device"] else ""
        dir_str = "->" if sample["direction"] == "read" else "<-"
        if sample.get("error"):
            err_name, err_desc = sample["error"]
            lines.append(f"{dev_str}0x{addr:05x} AUX {dir_str} (ret={sample['ret_size']:3d}) [{err_name} - {err_desc}]")
        else:
            data_hex = " ".join(f"{b:02x}" for b in sample["data"])
            lines.append(f"{dev_str}0x{addr:05x} AUX {dir_str} (ret= {sample['ret_size']:2d}) {data_hex}")
            if reg_info:
                for offset in range(len(sample["data"])):
                    offset_addr = addr + offset
                    offset_info = regs_db.get(offset_addr)
                    if offset_info:
                        decoded = decode_register(offset_info, sample["data"], addr, offset)
                        if decoded:
                            lines.append(decoded)
                    else:
                        byte_val = sample["data"][offset]
                        lines.append(f"0x{offset_addr:05x} (UNKNOWN): 0x{byte_val:02x}")
            else:
                for offset, byte_val in enumerate(sample["data"]):
                    lines.append(f"0x{addr + offset:05x} (UNKNOWN): 0x{byte_val:02x}")
        if len(elist) > 1:
            unique_vals = set()
            for e in elist:
                unique_vals.add(" ".join(f"{b:02x}" for b in e["data"]))
            if len(unique_vals) > 1:
                lines.append(f"    [{len(elist)} accesses, {len(unique_vals)} distinct values]")
                for i, e in enumerate(elist):
                    data_hex2 = " ".join(f"{b:02x}" for b in e["data"])
                    lines.append(f"    access#{i+1} @{e['timestamp']:.6f}s: {data_hex2}")
            else:
                lines.append(f"    [{len(elist)} identical accesses]")
        lines.append("")
    return "\n".join(lines)


def parse_sideband_header(data):
    if len(data) < 3:
        return None
    b0 = data[0]
    lct = (b0 >> 4) & 0xF
    lcr = b0 & 0xF
    rad_nibbles = lct - 1
    header_len = 2 + (rad_nibbles + 1) // 2
    if rad_nibbles % 2 == 1:
        header_len += 1
    header_len = max(3, header_len)
    if len(data) < header_len:
        return None
    rad = []
    rad_bytes = data[1:1 + (rad_nibbles + 1) // 2]
    for i, b in enumerate(rad_bytes):
        if len(rad) < rad_nibbles:
            rad.append((b >> 4) & 0xF)
        if len(rad) < rad_nibbles:
            rad.append(b & 0xF)
    ctrl_byte_idx = header_len - 1
    ctrl = data[ctrl_byte_idx]
    smt = (ctrl >> 7) & 1
    emt = (ctrl >> 6) & 1
    msn = (ctrl >> 4) & 1
    hdr_crc = ctrl & 0xF
    addr_byte_idx = header_len - 2
    addr_byte = data[addr_byte_idx]
    broadcast = (addr_byte >> 7) & 1
    path_msg = (addr_byte >> 6) & 1
    body_len = addr_byte & 0x3F
    return {
        "lct": lct,
        "lcr": lcr,
        "rad": rad,
        "broadcast": broadcast,
        "path_msg": path_msg,
        "body_len": body_len,
        "smt": smt,
        "emt": emt,
        "msn": msn,
        "hdr_crc": hdr_crc,
        "header_len": header_len,
    }


def concatenate_mst_reads(group, base):
    full_raw = []
    for e in group:
        offset = e["addr"] - base
        if offset >= len(full_raw):
            full_raw.extend([0] * (offset - len(full_raw)))
            full_raw.extend(e["data"])
        elif offset + len(e["data"]) > len(full_raw):
            existing_end = len(full_raw)
            new_bytes = e["data"][existing_end - offset:]
            full_raw.extend(new_bytes)
    return full_raw


def group_mst_entries(entries):
    mst_entries = [e for e in entries if classify_address(e["addr"]) in MST_BUFFER_TYPES]
    if not mst_entries:
        return {}

    entry_idx_map = {id(e): i for i, e in enumerate(entries)}

    by_base_dir = {}
    for e in mst_entries:
        base, _ = get_buffer_base(e["addr"])
        if base is None:
            continue
        key = (base, e["direction"])
        by_base_dir.setdefault(key, []).append(e)

    packet_groups = {}
    msg_counter = 0

    for (base, direction), entries_group in sorted(by_base_dir.items()):
        entries_sorted = sorted(entries_group, key=lambda x: (x["timestamp"] or 0, x["addr"]))

        msg_reads = []
        current = [entries_sorted[0]]
        for e in entries_sorted[1:]:
            ts = e["timestamp"] or 0
            prev_ts = current[-1]["timestamp"] or 0
            if ts - prev_ts > 0.003:
                msg_reads.append(current)
                current = [e]
            else:
                current.append(e)
        if current:
            msg_reads.append(current)

        pending_packets = []
        pending_indices = []

        for mr in msg_reads:
            full_raw = concatenate_mst_reads(mr, base)
            hdr = parse_sideband_header(full_raw)
            if hdr is None:
                continue

            body_data = full_raw[hdr["header_len"]:]
            data_only = body_data[:hdr["body_len"] - 1] if hdr["body_len"] > 0 else []
            crc8_val = body_data[hdr["body_len"] - 1] if hdr["body_len"] > 0 and len(body_data) >= hdr["body_len"] else None
            header_raw = full_raw[:hdr["header_len"]]

            hdr_crc_ok, body_crc_ok = verify_sideband_crc(header_raw, body_data[:hdr["body_len"]] if hdr["body_len"] > 0 else [], hdr["header_len"])


            mr_indices = [entry_idx_map.get(id(e), -1) for e in mr]
            pkt_info = {
                "header": hdr,
                "body_data": data_only,
                "crc8": crc8_val,
                "header_raw": header_raw,
                "hdr_crc_ok": hdr_crc_ok,
                "body_crc_ok": body_crc_ok,
                "entry_indices": mr_indices,
            }

            is_single = hdr["smt"] == 1 and hdr["emt"] == 1
            is_start = hdr["smt"] == 1 and hdr["emt"] == 0
            is_middle = hdr["smt"] == 0 and hdr["emt"] == 0
            is_end = hdr["smt"] == 0 and hdr["emt"] == 1

            if is_single:
                if pending_packets:
                    full_data = []
                    for pp in pending_packets:
                        full_data.extend(pp["body_data"])
                    msg = _make_msg(base, True, pending_packets, full_data, direction, pending_indices)
                    packet_groups[f"{base}_{direction}_{msg_counter}"] = msg
                    msg_counter += 1
                    pending_packets = []
                    pending_indices = []
                full_data = data_only[:]
                msg = _make_msg(base, False, [pkt_info], full_data, direction, mr_indices)
                packet_groups[f"{base}_{direction}_{msg_counter}"] = msg
                msg_counter += 1
            elif is_start:
                if pending_packets:
                    full_data = []
                    for pp in pending_packets:
                        full_data.extend(pp["body_data"])
                    msg = _make_msg(base, True, pending_packets, full_data, direction, pending_indices)
                    packet_groups[f"{base}_{direction}_{msg_counter}"] = msg
                    msg_counter += 1
                pending_packets = [pkt_info]
                pending_indices = list(mr_indices)
            elif is_middle or is_end:
                pending_packets.append(pkt_info)
                pending_indices.extend(mr_indices)
                if is_end:
                    full_data = []
                    for pp in pending_packets:
                        full_data.extend(pp["body_data"])
                    msg = _make_msg(base, True, pending_packets, full_data, direction, pending_indices)
                    packet_groups[f"{base}_{direction}_{msg_counter}"] = msg
                    msg_counter += 1
                    pending_packets = []
                    pending_indices = []

        if pending_packets:
            full_data = []
            for pp in pending_packets:
                full_data.extend(pp["body_data"])
            msg = _make_msg(base, True, pending_packets, full_data, direction, pending_indices)
            packet_groups[f"{base}_{direction}_{msg_counter}"] = msg
            msg_counter += 1

    return packet_groups


class PosBitReader:
    """BitReader wrapper that records byte/bit positions for each field read."""
    def __init__(self, data):
        self._reader = BitReader(data)
        self._data = data

    def read_bits(self, n):
        start = self._reader.bit_pos
        val = self._reader.read_bits(n)
        return val, self._reader.bit_spec(start, n)

    def read_byte(self):
        return self.read_bits(8)

    def read_bytes(self, n):
        start = self._reader.bit_pos
        result = []
        for _ in range(n):
            result.append(self._reader.read_byte())
        spec = self._reader.bit_spec(start, n * 8)
        return result, spec

    def remaining_bits(self):
        return self._reader.remaining_bits()

    def align_to_byte(self):
        self._reader.align_to_byte()

    @property
    def bit_pos(self):
        return self._reader.bit_pos


def _make_msg(base, is_multi, pkt_infos, full_data, direction="read", entry_indices=None):
    buf_name = classify_address(base)
    is_reply = buf_name in ("DOWN_REP", "UP_REP")
    msg = {
        "buffer": buf_name,
        "base_addr": base,
        "is_multi_packet": is_multi,
        "num_packets": len(pkt_infos),
        "packets": pkt_infos,
        "full_data": full_data,
        "direction": direction,
        "is_reply": is_reply,
        "entry_indices": entry_indices or [],
    }
    if full_data:
        if is_reply:
            msg["reply_type"] = "NAK" if (full_data[0] & 0x80) else "ACK"
            msg["request_id"] = full_data[0] & 0x7F
        else:
            msg["reply_type"] = None
            msg["request_id"] = full_data[0] & 0x7F
        msg["request_name"] = REQUEST_IDS.get(msg["request_id"], f"UNKNOWN(0x{msg['request_id']:02x})")
    hdr_crc_ok_all = all(p.get("hdr_crc_ok", True) for p in pkt_infos)
    body_crc_ok_all = all(p.get("body_crc_ok", True) for p in pkt_infos)
    if not hdr_crc_ok_all or not body_crc_ok_all:
        msg["crc_errors"] = []
        for i, p in enumerate(pkt_infos):
            if not p.get("hdr_crc_ok", True):
                msg["crc_errors"].append(f"pkt{i+1}: header CRC4 mismatch")
            if p.get("body_crc_ok") is False:
                msg["crc_errors"].append(f"pkt{i+1}: body CRC8 mismatch")
    return msg


def _fmt_guid(data):
    return " ".join(f"{b:02x}" for b in data)


def _fmt_dpcd_rev(val):
    major = (val >> 4) & 0xF
    minor = val & 0xF
    return f"{major}.{minor}"


def _parse_link_address_ack(reader):
    lines = []
    if reader.remaining_bits() < 8:
        lines.append("    (insufficient data)")
        return lines, None
    reader.read_bits(1)  # Reply_Type (0=ACK)
    reader.read_bits(7)  # Request_Identifier (0x01)
    if reader.remaining_bits() < 128 + 8:
        lines.append("    (insufficient data for GUID + nports)")
        return lines, None
    guid, guid_spec = reader.read_bytes(16)
    lines.append(f"    GUID[{guid_spec}]: {_fmt_guid(guid)}")
    reader.read_bits(4)  # reserved
    n_ports, nports_spec = reader.read_bits(4)
    lines.append(f"    Number_Of_Ports[{nports_spec}]: {n_ports}")
    topology_ports = []
    for p in range(n_ports):
        if reader.remaining_bits() < 16:
            lines.append(f"    (truncated at port {p})")
            break
        input_port, _ = reader.read_bits(1)
        peer_type, _ = reader.read_bits(3)
        port_num, portnum_spec = reader.read_bits(4)
        msg_cap, _ = reader.read_bits(1)
        dp_plug, _ = reader.read_bits(1)
        peer_name = PEER_DEVICE_TYPES.get(peer_type, f"Unknown({peer_type})")
        port_type = "Input" if input_port else "Output"
        lines.append(f"    Port {port_num}[{portnum_spec}] ({port_type}): {peer_name}")
        lines.append(f"      MST_Cap={msg_cap} DP_Plug={dp_plug}")
        ccs = None
        if peer_type == 5:
            if reader.remaining_bits() >= 128:
                ccs, ccs_spec = reader.read_bytes(16)
                lines.append(f"      CCS[{ccs_spec}]: {_fmt_guid(ccs)}")
            else:
                lines.append("      (truncated in CCS)")
                break
        port_info = {
            "port_num": port_num,
            "input_port": input_port,
            "peer_type": peer_type,
            "peer_name": peer_name,
            "msg_cap": msg_cap,
            "dp_plug": dp_plug,
        }
        if input_port == 0:
            if reader.remaining_bits() < 1:
                lines.append("      (truncated)")
                break
            legacy_plug, legacy_spec = reader.read_bits(1)
            lines.append(f"      Legacy_Plug[{legacy_spec}]: {legacy_plug}")
            if reader.remaining_bits() < 5 + 8:
                lines.append("      (truncated before DPCD_Revision)")
                break
            reader.read_bits(5)  # reserved
            dpcd_rev, rev_spec = reader.read_byte()
            lines.append(f"      DPCD_Revision[{rev_spec}]: {_fmt_dpcd_rev(dpcd_rev)}")
            port_info["dpcd_rev"] = dpcd_rev
            port_info["legacy_plug"] = legacy_plug
            if reader.remaining_bits() >= 128:
                peer_guid, guid_spec = reader.read_bytes(16)
                lines.append(f"      Peer_GUID[{guid_spec}]: {_fmt_guid(peer_guid)}")
                port_info["peer_guid"] = peer_guid
            else:
                lines.append("      (truncated before Peer_GUID)")
                break
            if reader.remaining_bits() >= 8:
                sdp_streams, streams_spec = reader.read_bits(4)
                sdp_sinks, sinks_spec = reader.read_bits(4)
                lines.append(f"      SDP_Streams[{streams_spec}]: {sdp_streams}")
                lines.append(f"      SDP_Sinks[{sinks_spec}]: {sdp_sinks}")
                port_info["sdp_streams"] = sdp_streams
                port_info["sdp_sinks"] = sdp_sinks
        else:
            if reader.remaining_bits() >= 6:
                reader.read_bits(6)
        topology_ports.append(port_info)
    return lines, {"guid": guid, "ports": topology_ports}


def _parse_connection_status_notify_request(reader):
    lines = []
    if reader.remaining_bits() < 16 + 128 + 8:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(4)
    guid, guid_spec = reader.read_bytes(16)
    reader.read_bits(1)
    legacy_plug, lp_spec = reader.read_bits(1)
    dp_plug, dp_spec = reader.read_bits(1)
    msg_cap, mc_spec = reader.read_bits(1)
    input_port, ip_spec = reader.read_bits(1)
    peer_type, pt_spec = reader.read_bits(3)
    peer_name = PEER_DEVICE_TYPES.get(peer_type, f"Unknown({peer_type})")
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    GUID[{guid_spec}]: {_fmt_guid(guid)}")
    lines.append(f"    Input_Port[{ip_spec}]={input_port} Peer_Type[{pt_spec}]={peer_name}")
    lines.append(f"    DP_Plug[{dp_spec}]={dp_plug} Legacy_Plug[{lp_spec}]={legacy_plug} MST_Cap[{mc_spec}]={msg_cap}")
    return lines


def _parse_enum_path_resources_ack(reader):
    lines = []
    if reader.remaining_bits() < 48:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(3)
    fec, fec_spec = reader.read_bits(1)
    full_pbn, fpbn_spec = reader.read_bits(16)
    avail_pbn, apbn_spec = reader.read_bits(16)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    FEC_Capability[{fec_spec}]: {fec} ({'supported' if fec else 'not supported'})")
    lines.append(f"    Full_PBN[{fpbn_spec}]: {full_pbn}")
    lines.append(f"    Available_PBN[{apbn_spec}]: {avail_pbn}")
    return lines


def _parse_allocate_payload_request(reader):
    lines = []
    if reader.remaining_bits() < 48:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    n_sdp, nsdp_spec = reader.read_bits(4)
    reader.read_bits(1)
    vc_id, vc_spec = reader.read_bits(7)
    pbn, pbn_spec = reader.read_bits(16)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    Number_SDP_Streams[{nsdp_spec}]: {n_sdp}")
    lines.append(f"    VC_Payload_ID[{vc_spec}]: {vc_id}")
    lines.append(f"    PBN[{pbn_spec}]: {pbn}")
    for i in range(n_sdp):
        if reader.remaining_bits() < 4:
            break
        sdp_sink, sink_spec = reader.read_bits(4)
        lines.append(f"    SDP_Stream_Sink[{i}][{sink_spec}]: {sdp_sink}")
    return lines


def _parse_allocate_payload_ack(reader):
    lines = []
    if reader.remaining_bits() < 48:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(5)
    vc_id, vc_spec = reader.read_bits(7)
    alloc_pbn, pbn_spec = reader.read_bits(16)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    VC_Payload_ID[{vc_spec}]: {vc_id}")
    lines.append(f"    Allocated_PBN[{pbn_spec}]: {alloc_pbn}")
    return lines


def _parse_query_payload_ack(reader):
    lines = []
    if reader.remaining_bits() < 40:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(4)  # zeros
    alloc_pbn, pbn_spec = reader.read_bits(16)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    Allocated_PBN[{pbn_spec}]: {alloc_pbn}")
    return lines


def _parse_resource_status_notify_request(reader):
    lines = []
    if reader.remaining_bits() < 16 + 128 + 16:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(4)
    guid, guid_spec = reader.read_bytes(16)
    avail_pbn, pbn_spec = reader.read_bits(16)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    GUID[{guid_spec}]: {_fmt_guid(guid)}")
    lines.append(f"    Available_PBN[{pbn_spec}]: {avail_pbn}")
    return lines


def _parse_remote_dpcd_read_request(reader):
    lines = []
    if reader.remaining_bits() < 48:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    dpcd_addr, addr_spec = reader.read_bits(20)
    n_bytes, nb_spec = reader.read_byte()
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    DPCD_Address[{addr_spec}]: 0x{dpcd_addr:05x}")
    lines.append(f"    Bytes_To_Read[{nb_spec}]: {n_bytes}")
    return lines


def _parse_remote_dpcd_read_ack(reader):
    lines = []
    if reader.remaining_bits() < 32:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    reader.read_bits(4)  # zeros
    port_num, pn_spec = reader.read_bits(4)
    n_read, nr_spec = reader.read_byte()
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    Bytes_Read[{nr_spec}]: {n_read}")
    data, _ = reader.read_bytes(min(n_read, reader.remaining_bits() // 8))
    if data:
        data_hex = " ".join(f"{b:02x}" for b in data)
        lines.append(f"    Data: {data_hex}")
    return lines


def _parse_remote_dpcd_write_request(reader):
    lines = []
    if reader.remaining_bits() < 40:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    dpcd_addr, addr_spec = reader.read_bits(20)
    n_bytes, nb_spec = reader.read_byte()
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    DPCD_Address[{addr_spec}]: 0x{dpcd_addr:05x}")
    lines.append(f"    Bytes_To_Write[{nb_spec}]: {n_bytes}")
    data, _ = reader.read_bytes(min(n_bytes, reader.remaining_bits() // 8))
    if data:
        data_hex = " ".join(f"{b:02x}" for b in data)
        lines.append(f"    Data: {data_hex}")
    return lines


def _parse_remote_dpcd_write_ack(reader):
    lines = []
    if reader.remaining_bits() < 24:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    reader.read_bits(4)  # zeros
    port_num, pn_spec = reader.read_bits(4)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    return lines


def _parse_remote_i2c_read_request(reader):
    lines = []
    if reader.remaining_bits() < 24:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(2)
    n_trans_enc, nt_spec = reader.read_bits(2)
    n_trans = n_trans_enc + 1  # DP spec: field value is (N-1), actual count is N
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    Number_Of_I2C_Transactions[{nt_spec}]: {n_trans} (encoded={n_trans_enc})")
    for i in range(n_trans - 1):
        if reader.remaining_bits() < 16:
            break
        reader.read_bits(1)
        dev_id, dev_spec = reader.read_bits(7)
        n_write, nw_spec = reader.read_byte()
        lines.append(f"    I2C_Write[{i}]: Device=0x{dev_id:02x} Bytes={n_write}")
        write_data, wd_spec = reader.read_bytes(min(n_write, reader.remaining_bits() // 8))
        if write_data:
            lines.append(f"    I2C_Write_Data[{i}]: {' '.join(f'{b:02x}' for b in write_data)}")
        if reader.remaining_bits() < 8:
            break
        reader.read_bits(3)
        no_stop, ns_spec = reader.read_bits(1)
        delay, dly_spec = reader.read_bits(4)
        lines.append(f"    No_Stop_Bit[{ns_spec}]: {no_stop} (no STOP if 1)")
        if delay:
            lines.append(f"    I2C_Transaction_Delay[{dly_spec}]: {delay} us")
    if reader.remaining_bits() < 16:
        return lines
    reader.read_bits(1)
    dev_id, dev_spec = reader.read_bits(7)
    n_read, nr_spec = reader.read_byte()
    lines.append(f"    I2C_Read: Device=0x{dev_id:02x} Bytes={n_read}")
    return lines


def _parse_remote_i2c_read_ack(reader):
    lines = []
    if reader.remaining_bits() < 32:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    reader.read_bits(4)  # zeros
    port_num, pn_spec = reader.read_bits(4)
    n_read, nr_spec = reader.read_byte()
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    Bytes_Read[{nr_spec}]: {n_read}")
    data, _ = reader.read_bytes(min(n_read, reader.remaining_bits() // 8))
    for chunk_start in range(0, len(data), 16):
        chunk = data[chunk_start:chunk_start + 16]
        lines.append(f"    Data[{chunk_start:3d}]: {' '.join(f'{b:02x}' for b in chunk)}")
    if n_read == 128 or n_read == 256:
        lines.append(f"    (EDID data, {n_read} bytes)")
    return lines


def _parse_remote_i2c_write_request(reader):
    lines = []
    if reader.remaining_bits() < 32:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(5)
    dev_id, dev_spec = reader.read_bits(7)
    n_write, nw_spec = reader.read_byte()
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    lines.append(f"    I2C_Device[{dev_spec}]: 0x{dev_id:02x}")
    lines.append(f"    Bytes_To_Write[{nw_spec}]: {n_write}")
    data, _ = reader.read_bytes(min(n_write, reader.remaining_bits() // 8))
    if data:
        lines.append(f"    Data: {' '.join(f'{b:02x}' for b in data)}")
    return lines


def _parse_remote_i2c_write_ack(reader):
    lines = []
    if reader.remaining_bits() < 24:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    reader.read_bits(4)  # zeros
    port_num, pn_spec = reader.read_bits(4)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    return lines


def _parse_power_phy_request(reader):
    lines = []
    if reader.remaining_bits() < 24:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    reader.read_bits(4)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    return lines


def _parse_power_phy_ack(reader):
    lines = []
    if reader.remaining_bits() < 24:
        lines.append("    (insufficient data)")
        return lines
    reader.read_byte()  # Skip Request ID byte
    port_num, pn_spec = reader.read_bits(4)
    lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
    return lines


def _parse_nak_detail(reader):
    lines = []
    if reader.remaining_bits() < 128 + 24:
        lines.append("    (insufficient data for NAK)")
        return lines
    reader.read_byte()  # Skip Reply_Type + Request_ID byte
    guid, guid_spec = reader.read_bytes(16)
    reason, reason_spec = reader.read_byte()
    nak_data, nd_spec = reader.read_byte()
    reason_name = NAK_REASONS.get(reason, f"Unknown(0x{reason:02x})")
    lines.append(f"    GUID[{guid_spec}]: {_fmt_guid(guid)}")
    lines.append(f"    NAK_Reason[{reason_spec}]: {reason_name} (0x{reason:02x})")
    lines.append(f"    NAK_Data[{nd_spec}]: 0x{nak_data:02x}")
    return lines


def parse_mt_detail(msg):
    lines = []
    fd = msg["full_data"]
    req_id = msg.get("request_id")
    reply = msg.get("reply_type")
    is_reply = msg.get("is_reply", False)
    if req_id is None or len(fd) < 1:
        return lines, None
    reader = PosBitReader(fd)
    topology = None

    if is_reply and reply == "ACK":
        if req_id == 0x01:
            lines.append("  LINK_ADDRESS ACK detail:")
            detail_lines, topology = _parse_link_address_ack(reader)
            lines.extend(detail_lines)
        elif req_id == 0x02:
            lines.append("  CONNECTION_STATUS_NOTIFY ACK (no data)")
        elif req_id == 0x10:
            lines.append("  ENUM_PATH_RESOURCES ACK detail:")
            lines.extend(_parse_enum_path_resources_ack(reader))
        elif req_id == 0x11:
            lines.append("  ALLOCATE_PAYLOAD ACK detail:")
            lines.extend(_parse_allocate_payload_ack(reader))
        elif req_id == 0x12:
            lines.append("  QUERY_PAYLOAD ACK detail:")
            lines.extend(_parse_query_payload_ack(reader))
        elif req_id == 0x13:
            lines.append("  RESOURCE_STATUS_NOTIFY ACK (no data)")
        elif req_id == 0x14:
            lines.append("  CLEAR_PAYLOAD_ID_TABLE ACK (no data)")
        elif req_id == 0x20:
            lines.append("  REMOTE_DPCD_READ ACK detail:")
            lines.extend(_parse_remote_dpcd_read_ack(reader))
        elif req_id == 0x21:
            lines.append("  REMOTE_DPCD_WRITE ACK detail:")
            lines.extend(_parse_remote_dpcd_write_ack(reader))
        elif req_id == 0x22:
            lines.append("  REMOTE_I2C_READ ACK detail:")
            lines.extend(_parse_remote_i2c_read_ack(reader))
        elif req_id == 0x23:
            lines.append("  REMOTE_I2C_WRITE ACK detail:")
            lines.extend(_parse_remote_i2c_write_ack(reader))
        elif req_id == 0x24:
            lines.append("  POWER_UP_PHY ACK detail:")
            lines.extend(_parse_power_phy_ack(reader))
        elif req_id == 0x25:
            lines.append("  POWER_DOWN_PHY ACK detail:")
            lines.extend(_parse_power_phy_ack(reader))
        elif req_id == 0x00:
            lines.append("  GET_MESSAGE_TRANSACTION_VERSION ACK detail:")
            if reader.remaining_bits() >= 8:
                ver, ver_spec = reader.read_byte()
                lines.append(f"    Version[{ver_spec}]: 0x{ver:02x} ({'DP 1.2a' if ver == 1 else 'DP 1.3/1.4a' if ver == 2 else 'unknown'})")
        else:
            lines.append(f"  (unhandled ACK request 0x{req_id:02x})")
    elif is_reply and reply == "NAK":
        lines.append("  NAK detail:")
        lines.extend(_parse_nak_detail(reader))
    elif not is_reply:
        if req_id == 0x01:
            lines.append("  LINK_ADDRESS Request (no data)")
        elif req_id == 0x02:
            lines.append("  CONNECTION_STATUS_NOTIFY Request detail:")
            lines.extend(_parse_connection_status_notify_request(reader))
        elif req_id == 0x10:
            lines.append("  ENUM_PATH_RESOURCES Request detail:")
            if reader.remaining_bits() >= 16:
                reader.read_byte()  # Skip Request ID byte
                port_num, pn_spec = reader.read_bits(4)
                lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
        elif req_id == 0x11:
            lines.append("  ALLOCATE_PAYLOAD Request detail:")
            lines.extend(_parse_allocate_payload_request(reader))
        elif req_id == 0x12:
            lines.append("  QUERY_PAYLOAD Request detail:")
            if reader.remaining_bits() >= 32:
                reader.read_byte()  # Skip Request ID byte
                port_num, pn_spec = reader.read_bits(4)
                reader.read_bits(5)
                vc_id, vc_spec = reader.read_bits(7)
                lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
                lines.append(f"    VC_Payload_ID[{vc_spec}]: {vc_id}")
        elif req_id == 0x13:
            lines.append("  RESOURCE_STATUS_NOTIFY Request detail:")
            lines.extend(_parse_resource_status_notify_request(reader))
        elif req_id == 0x14:
            lines.append("  CLEAR_PAYLOAD_ID_TABLE (broadcast, no data)")
        elif req_id == 0x20:
            lines.append("  REMOTE_DPCD_READ Request detail:")
            lines.extend(_parse_remote_dpcd_read_request(reader))
        elif req_id == 0x21:
            lines.append("  REMOTE_DPCD_WRITE Request detail:")
            lines.extend(_parse_remote_dpcd_write_request(reader))
        elif req_id == 0x22:
            lines.append("  REMOTE_I2C_READ Request detail:")
            lines.extend(_parse_remote_i2c_read_request(reader))
        elif req_id == 0x23:
            lines.append("  REMOTE_I2C_WRITE Request detail:")
            lines.extend(_parse_remote_i2c_write_request(reader))
        elif req_id == 0x24:
            lines.append("  POWER_UP_PHY Request detail:")
            lines.extend(_parse_power_phy_request(reader))
        elif req_id == 0x25:
            lines.append("  POWER_DOWN_PHY Request detail:")
            lines.extend(_parse_power_phy_request(reader))
        elif req_id == 0x00:
            lines.append("  GET_MESSAGE_TRANSACTION_VERSION Request:")
            if reader.remaining_bits() >= 16:
                reader.read_byte()  # Skip Request ID byte
                port_num, pn_spec = reader.read_bits(4)
                lines.append(f"    Port_Number[{pn_spec}]: {port_num}")
        else:
            lines.append(f"  (unhandled request 0x{req_id:02x})")
    else:
        lines.append(f"  (unexpected state: reply={reply}, is_reply={is_reply}, req_id=0x{req_id:02x})")

    return lines, topology


def pair_messages(messages):
    pairs = []
    reqs = {}
    for key in sorted(messages.keys()):
        msg = messages[key]
        if msg.get("request_id") is None:
            continue
        is_req = not msg.get("is_reply", False)
        is_rep = msg.get("is_reply", False)
        msn = None
        if msg["packets"]:
            msn = msg["packets"][0]["header"].get("msn")
        if is_req:
            req_key = (msg["request_id"], msn, msg["buffer"])
            reqs[req_key] = msg
        elif is_rep:
            req_pair_key = None
            for rk, rv in reqs.items():
                if rk[0] == msg["request_id"]:
                    if (msg["buffer"] == "DOWN_REP" and rv["buffer"] == "DOWN_REQ") or \
                       (msg["buffer"] == "UP_REP" and rv["buffer"] == "UP_REQ"):
                        req_pair_key = rk
                        break
            if req_pair_key:
                pairs.append((reqs.pop(req_pair_key), msg))
            else:
                pairs.append((None, msg))
        else:
            pairs.append((msg, None))
    for key, msg in reqs.items():
        pairs.append((msg, None))
    return pairs


def build_topology_tree(messages):
    topologies = []
    for key in sorted(messages.keys()):
        msg = messages[key]
        if msg.get("request_id") != 0x01 or not msg.get("is_reply", False) or msg.get("reply_type") != "ACK":
            continue
        _, topology = parse_mt_detail(msg)
        if topology:
            topologies.append(topology)

    if not topologies:
        return []

    lines = []
    for topo in topologies:
        guid_str = _fmt_guid(topology["guid"])
        oui = f"{topology['guid'][0]:02x}{topology['guid'][1]:02x}{topology['guid'][2]:02x}"
        lines.append(f"Branch Device (GUID: {guid_str}, OUI: {oui})")
        for port in topology["ports"]:
            ptype = "Input" if port["input_port"] else "Output"
            plug_status = "connected" if port["dp_plug"] else "disconnected"
            line = f"  +- Port {port['port_num']} ({ptype}): {port['peer_name']}"
            if port["input_port"] == 0:
                line += f", Legacy={port.get('legacy_plug', '?')}"
                if "dpcd_rev" in port:
                    line += f", DPCD {_fmt_dpcd_rev(port['dpcd_rev'])}"
                if "sdp_streams" in port:
                    line += f", Streams={port['sdp_streams']}/Sinks={port['sdp_sinks']}"
            else:
                line += f", MST_Cap={port['msg_cap']}, {plug_status}"
            lines.append(line)
    return lines


def generate_key_findings(entries, messages):
    lines = []
    topologies = []
    for key in sorted(messages.keys()):
        msg = messages[key]
        if msg.get("request_id") == 0x01 and msg.get("reply_type") == "ACK":
            _, topology = parse_mt_detail(msg)
            if topology:
                topologies.append(topology)

    if topologies:
        lines.append("MST Topology:")
        tree_lines = build_topology_tree(messages)
        lines.extend(tree_lines)

    naks = []
    for key in sorted(messages.keys()):
        msg = messages[key]
        if msg.get("reply_type") == "NAK":
            naks.append(msg)
    if naks:
        lines.append("")
        lines.append(f"NAK messages: {len(naks)}")
        for msg in naks:
            fd = msg["full_data"]
            req_name = msg.get("request_name", "?")
            if len(fd) >= 19:
                reason = fd[17]
                reason_name = NAK_REASONS.get(reason, f"Unknown(0x{reason:02x})")
                lines.append(f"  {req_name}: NAK reason={reason_name}")
            else:
                lines.append(f"  {req_name}: NAK (truncated)")

    crc_errors = []
    for key in sorted(messages.keys()):
        msg = messages[key]
        if "crc_errors" in msg:
            crc_errors.extend(msg["crc_errors"])
    if crc_errors:
        lines.append("")
        lines.append(f"CRC errors: {len(crc_errors)}")
        for ce in crc_errors:
            lines.append(f"  {ce}")

    errors = [e for e in entries if e.get("error")]
    if errors:
        lines.append("")
        lines.append(f"AUX errors: {len(errors)}")
        for e in errors:
            err_name, err_desc = e["error"]
            lines.append(f"  0x{e['addr']:05x}: {err_name} - {err_desc} (ret={e['ret_size']})")

    return lines




def _build_mst_index(messages):
    """Build a mapping from entry index to (msg, pkt_idx) for MST entries."""
    mst_index = {}
    for key in sorted(messages.keys()):
        msg = messages[key]
        for pkt_idx, pkt in enumerate(msg.get("packets", [])):
            for entry_idx in pkt.get("entry_indices", []):
                if entry_idx >= 0:
                    mst_index[entry_idx] = {"msg": msg, "pkt_idx": pkt_idx}
    return mst_index


def _fmt_single_entry_header(e, idx):
    parts = [f"[#{idx+1}]"]
    if e.get("timestamp") is not None:
        parts.append(f"@{e['timestamp']:.6f}s")
    dev = e.get("device")
    if dev:
        parts.append(f"{dev}:")
    dir_str = "->" if e["direction"] == "read" else "<-"
    addr_cat = classify_address(e["addr"])
    if e.get("error"):
        err_name, err_desc = e["error"]
        parts.append(f"0x{e['addr']:05x}({addr_cat}) AUX {dir_str} (ret={e['ret_size']:3d}) [{err_name} - {err_desc}]")
    else:
        data_hex = " ".join(f"{b:02x}" for b in e["data"])
        parts.append(f"0x{e['addr']:05x}({addr_cat}) AUX {dir_str} (ret= {e['ret_size']:2d}) {data_hex}")
    return " ".join(parts)


def format_sequential_output(entries, messages, regs_db):
    lines = []
    mst_index = _build_mst_index(messages)
    mst_emitted = set()
    pair_map = {}
    pairs = pair_messages(messages)
    for req_msg, rep_msg in pairs:
        if req_msg:
            pair_map[id(req_msg)] = rep_msg
        if rep_msg:
            pair_map[id(rep_msg)] = req_msg

    for idx, e in enumerate(entries):
        raw = e.get("raw_line", "")
        if raw:
            lines.append(f"  {raw}")
        else:
            lines.append(f"  {_fmt_single_entry_header(e, idx)}")

        addr_cat = classify_address(e["addr"])

        if addr_cat in MST_BUFFER_TYPES:
            mst_info = mst_index.get(idx)
            if mst_info is not None:
                msg = mst_info["msg"]
                pkt_idx = mst_info["pkt_idx"]
                pkt = msg["packets"][pkt_idx]
                hdr = pkt["header"]
                all_indices = msg.get("entry_indices", [])
                is_last_entry_of_msg = (idx == all_indices[-1]) if all_indices else False

                # Show packet header for every entry
                pkt_label = f"Packet {pkt_idx+1}/{msg['num_packets']}"
                if msg["is_multi_packet"]:
                    if hdr["smt"] == 1 and hdr["emt"] == 0:
                        pkt_label += " (START)"
                    elif hdr["smt"] == 0 and hdr["emt"] == 0:
                        pkt_label += " (MIDDLE)"
                    elif hdr["smt"] == 0 and hdr["emt"] == 1:
                        pkt_label += " (END)"
                crc_status = ""
                if not pkt.get("hdr_crc_ok", True):
                    crc_status += " [HDR_CRC4_FAIL]"
                if pkt.get("body_crc_ok") is False:
                    crc_status += " [BODY_CRC8_FAIL]"
                data_hex = " ".join(f"{b:02x}" for b in pkt["body_data"])
                lines.append(f"  {pkt_label}:")
                lines.append(f"    Header: LCT={hdr['lct']} LCR={hdr['lcr']} "
                             f"RAD={hdr['rad']} BC={hdr['broadcast']} Path={hdr['path_msg']} "
                             f"BodyLen={hdr['body_len']} SMT={hdr['smt']} EMT={hdr['emt']} "
                             f"MSN={hdr['msn']} CRC4=0x{hdr['hdr_crc']:x}{crc_status}")
                if data_hex:
                    lines.append(f"    Body data: {data_hex}")
                if pkt.get("crc8") is not None:
                    lines.append(f"    CRC-8: 0x{pkt['crc8']:02x}")

                # Show full message assembly + MT detail on LAST entry
                if is_last_entry_of_msg:
                    lines.append(f"  ── MST Sideband Message ({msg['buffer']} 0x{msg['base_addr']:05x}) ──")
                    lines.extend(_format_one_mst_msg(msg, pair_map))
        elif addr_cat in ("DPCD_REGISTER", "ESI", "EXTENDED_RECEIVER_CAP",
                          "DEVICE_SPECIFIC_PARAMS", "PROTOCOL_CONVERTER",
                          "DSC_ENCODER", "LTTPR_REPEATER"):
            if not e.get("error") and e["data"]:
                lines.extend(_decode_dpcd_entry(e, regs_db))

        lines.append("")

    return "\n".join(lines)


def _decode_dpcd_entry(e, regs_db):
    lines = []
    addr = e["addr"]
    data = e["data"]
    for offset in range(len(data)):
        offset_addr = addr + offset
        reg_info = regs_db.get(offset_addr)
        if reg_info:
            decoded = decode_register(reg_info, data, addr, offset)
            if decoded:
                for dl in decoded.splitlines():
                    lines.append(f"  {dl}")
        else:
            byte_val = data[offset]
            lines.append(f"  0x{offset_addr:05x} (UNKNOWN): 0x{byte_val:02x}")
    return lines


def _format_one_mst_msg(msg, pair_map=None):
    lines = []
    is_reply = msg.get("is_reply", False)
    if is_reply:
        buf_dir = "-> Source reads" if msg["buffer"] in ("DOWN_REP", "UP_REQ") else "<- Source writes"
    else:
        buf_dir = "<- Source writes" if msg["buffer"] in ("DOWN_REQ", "UP_REP") else "-> Source reads"
    msg_type = "Reply" if is_reply else "Request"
    lines.append(f"  {msg['buffer']} (0x{msg['base_addr']:05x}) {buf_dir} [{msg_type}]")
    if msg["is_multi_packet"]:
        lines.append(f"  Multi-packet message: {msg['num_packets']} packets")
    for i, pkt in enumerate(msg["packets"]):
        hdr = pkt["header"]
        pkt_label = f"Packet {i+1}/{msg['num_packets']}" if msg["is_multi_packet"] else "Packet"
        if msg["is_multi_packet"]:
            if hdr["smt"] == 1 and hdr["emt"] == 0:
                pkt_label += " (START)"
            elif hdr["smt"] == 0 and hdr["emt"] == 0:
                pkt_label += " (MIDDLE)"
            elif hdr["smt"] == 0 and hdr["emt"] == 1:
                pkt_label += " (END)"
        lines.append(f"  {pkt_label}:")
        crc_status = ""
        if not pkt.get("hdr_crc_ok", True):
            crc_status += " [HDR_CRC4_FAIL]"
        if pkt.get("body_crc_ok") is False:
            crc_status += " [BODY_CRC8_FAIL]"
        # Sideband header byte/bit positions per DP spec
        # Byte 0: [7:4] LCT, [3:0] LCR
        # Byte 1..N-2: RAD nibbles
        # Byte N-2: [7] Broadcast, [6] Path, [5:0] BodyLen
        # Byte N-1: [7] SMT, [6] EMT, [5] 0, [4] MSN, [3:0] CRC4
        lines.append(f"    Header (byte positions):")
        lines.append(f"      Byte 0 [7:4] LCT={hdr['lct']}, [3:0] LCR={hdr['lcr']}")
        rad_str = ", ".join(f"Nib{chr(65+i)}={n:x}" for i, n in enumerate(hdr['rad'])) if hdr['rad'] else "(none)"
        lines.append(f"      Byte 1..N-2 [{rad_str}] RAD={hdr['rad']}")
        lines.append(f"      Byte N-2 [7] BC={hdr['broadcast']} [6] Path={hdr['path_msg']} [5:0] BodyLen={hdr['body_len']}")
        lines.append(f"      Byte N-1 [7] SMT={hdr['smt']} [6] EMT={hdr['emt']} [4] MSN={hdr['msn']} [3:0] CRC4=0x{hdr['hdr_crc']:x}{crc_status}")
        data_hex = " ".join(f"{b:02x}" for b in pkt["body_data"])
        if data_hex:
            lines.append(f"    Body data: {data_hex}")
        if pkt.get("crc8") is not None:
            lines.append(f"    CRC-8: 0x{pkt['crc8']:02x}")
    if msg["full_data"]:
        fd = msg["full_data"]
        fd_hex = " ".join(f"{b:02x}" for b in fd)
        lines.append(f"  Assembled MT ({len(fd)} bytes):")
        for chunk_start in range(0, len(fd_hex), 96):
            lines.append(f"    {fd_hex[chunk_start:chunk_start+96]}")
        # MT header byte/bit breakdown
        if len(fd) >= 1:
            b0 = fd[0]
            if is_reply:
                reply_bit = (b0 >> 7) & 1
                req_id = b0 & 0x7F
                lines.append(f"  MT Byte[0]: [7] reply={reply_bit} ({'NAK' if reply_bit else 'ACK'}), [6:0] request_id=0x{req_id:02x} ({msg.get('request_name', '?')})")
            else:
                zero_bit = (b0 >> 7) & 1
                req_id = b0 & 0x7F
                lines.append(f"  MT Byte[0]: [7] zero={zero_bit}, [6:0] request_id=0x{req_id:02x} ({msg.get('request_name', '?')})")
        if is_reply:
            if "reply_type" in msg:
                lines.append(f"  Reply: {msg['reply_type']}, Request: {msg['request_name']} (0x{msg['request_id']:02x})")
        else:
            lines.append(f"  Request: {msg['request_name']} (0x{msg['request_id']:02x})")
        detail_lines, _ = parse_mt_detail(msg)
        for dl in detail_lines:
            lines.append(f"  {dl}")

    if pair_map:
        paired = pair_map.get(id(msg))
        if paired:
            paired_type = "Reply" if paired.get("is_reply") else "Request"
            parts = [paired['buffer'], paired_type]
            if paired.get('reply_type'):
                parts.append(paired['reply_type'])
            if paired.get('request_name'):
                parts.append(paired['request_name'])
            lines.append(f"  [Paired with: {' '.join(parts)}]")
    return lines

def format_mst_messages(messages):
    lines = []
    pairs = pair_messages(messages)
    for req_msg, rep_msg in pairs:
        for msg in (req_msg, rep_msg):
            if msg is None:
                continue
            is_reply = msg.get("is_reply", False)
            if is_reply:
                buf_dir = "-> Source reads" if msg["buffer"] in ("DOWN_REP", "UP_REQ") else "<- Source writes"
            else:
                buf_dir = "<- Source writes" if msg["buffer"] in ("DOWN_REQ", "UP_REP") else "-> Source reads"
            msg_type = "Reply" if is_reply else "Request"
            lines.append(f"=== {msg['buffer']} (0x{msg['base_addr']:05x}) {buf_dir} [{msg_type}] ===")
            if msg["is_multi_packet"]:
                lines.append(f"Multi-packet message: {msg['num_packets']} packets")
            else:
                lines.append(f"Single-packet message")
            for i, pkt in enumerate(msg["packets"]):
                hdr = pkt["header"]
                pkt_label = f"Packet {i+1}/{msg['num_packets']}" if msg["is_multi_packet"] else "Packet"
                if msg["is_multi_packet"]:
                    if hdr["smt"] == 1 and hdr["emt"] == 0:
                        pkt_label += " (START)"
                    elif hdr["smt"] == 0 and hdr["emt"] == 0:
                        pkt_label += " (MIDDLE)"
                    elif hdr["smt"] == 0 and hdr["emt"] == 1:
                        pkt_label += " (END)"
                lines.append(f"  {pkt_label}:")
                crc_status = ""
                if not pkt.get("hdr_crc_ok", True):
                    crc_status += " [HDR_CRC4_FAIL]"
                if pkt.get("body_crc_ok") is False:
                    crc_status += " [BODY_CRC8_FAIL]"
                lines.append(f"    Header: LCT={hdr['lct']} LCR={hdr['lcr']} "
                             f"RAD={hdr['rad']} BC={hdr['broadcast']} Path={hdr['path_msg']} "
                             f"BodyLen={hdr['body_len']} SMT={hdr['smt']} EMT={hdr['emt']} "
                             f"MSN={hdr['msn']} CRC4=0x{hdr['hdr_crc']:x}{crc_status}")
                data_hex = " ".join(f"{b:02x}" for b in pkt["body_data"])
                if data_hex:
                    lines.append(f"    Body data: {data_hex}")
                if pkt.get("crc8") is not None:
                    lines.append(f"    CRC-8: 0x{pkt['crc8']:02x}")
            if msg["full_data"]:
                lines.append(f"  Assembled MT ({len(msg['full_data'])} bytes):")
                fd = msg["full_data"]
                fd_hex = " ".join(f"{b:02x}" for b in fd)
                for chunk_start in range(0, len(fd_hex), 96):
                    lines.append(f"    {fd_hex[chunk_start:chunk_start+96]}")
                if is_reply:
                    if "reply_type" in msg:
                        lines.append(f"  Reply: {msg['reply_type']}, Request: {msg['request_name']} (0x{msg['request_id']:02x})")
                else:
                    lines.append(f"  Request: {msg['request_name']} (0x{msg['request_id']:02x})")
                detail_lines, _ = parse_mt_detail(msg)
                lines.extend(detail_lines)
            lines.append("")
        if req_msg and rep_msg:
            lines.append(f"  [Paired: {req_msg['request_name']} REQ -> {rep_msg.get('reply_type', '?')} REP]")
            lines.append("")
    return "\n".join(lines)


def generate_summary(entries, messages):
    lines = []
    total = len(entries)
    reads = sum(1 for e in entries if e["direction"] == "read")
    writes = sum(1 for e in entries if e["direction"] == "write")
    timestamps = [e["timestamp"] for e in entries if e["timestamp"] is not None]
    time_span = f"{min(timestamps):.6f}s - {max(timestamps):.6f}s" if timestamps else "N/A"
    dpcd_count = sum(1 for e in entries if classify_address(e["addr"]) == "DPCD_REGISTER")
    esi_count = sum(1 for e in entries if classify_address(e["addr"]) == "ESI")
    ext_cap_count = sum(1 for e in entries if classify_address(e["addr"]) == "EXTENDED_RECEIVER_CAP")
    pcon_count = sum(1 for e in entries if classify_address(e["addr"]) == "PROTOCOL_CONVERTER")
    lttpr_count = sum(1 for e in entries if classify_address(e["addr"]) == "LTTPR_REPEATER")
    mst_count = sum(1 for e in entries if classify_address(e["addr"]) in MST_BUFFER_TYPES)
    lines.append(f"Total entries: {total}")
    lines.append(f"  DPCD register accesses: {dpcd_count}")
    lines.append(f"  ESI accesses: {esi_count}")
    if ext_cap_count:
        lines.append(f"  Extended Receiver Cap: {ext_cap_count}")
    if pcon_count:
        lines.append(f"  Protocol Converter: {pcon_count}")
    if lttpr_count:
        lines.append(f"  LTTPR Repeater: {lttpr_count}")
    lines.append(f"  MST sideband messages: {mst_count}")
    lines.append(f"  Reads: {reads}, Writes: {writes}")
    lines.append(f"  Time span: {time_span}")
    errors = [e for e in entries if e.get("error")]
    if errors:
        lines.append(f"  AUX errors: {len(errors)}")
        for e in errors:
            err_name, err_desc = e["error"]
            lines.append(f"    0x{e['addr']:05x} {e['direction']}: {err_name} - {err_desc} (ret={e['ret_size']})")
    lines.append(f"MST messages parsed: {len(messages)}")
    pairs = pair_messages(messages)
    for req_msg, rep_msg in pairs:
        req_name = req_msg.get("request_name", "?") if req_msg else "?"
        if rep_msg:
            reply = rep_msg.get("reply_type", "?") or "Reply"
            buf = rep_msg["buffer"]
            multi = f"({rep_msg['num_packets']} pkt)" if rep_msg["is_multi_packet"] else "(1 pkt)"
        elif req_msg:
            reply = "Request"
            buf = req_msg["buffer"]
            multi = f"({req_msg['num_packets']} pkt)" if req_msg["is_multi_packet"] else "(1 pkt)"
        else:
            continue
        lines.append(f"  {buf} {reply} {req_name} {multi}")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parse DP MST DPCD logs")
    parser.add_argument("logfile", nargs="?", help="Log file path (default: stdin)")
    parser.add_argument("--format", choices=["auto", "drm_dp_dump", "rockchip", "hex_dump"],
                        default="auto", help="Input log format (default: auto-detect)")
    parser.add_argument("--base-addr", type=lambda x: int(x, 0),
                        default=0x00000,
                        help="Base DPCD address for hex_dump format (default: 0x00000)")
    parser.add_argument("--grouped", action="store_true",
                        help="Use grouped MST message output (default: sequential per-entry output)")
    args = parser.parse_args()

    text = open(args.logfile).read() if args.logfile else sys.stdin.read()

    fmt = args.format
    if fmt == "auto":
        fmt = detect_format(text)

    if fmt == "hex_dump":
        entries = parse_hex_dump(text, args.base_addr)
    elif fmt == "drm_dp_dump":
        entries = parse_drm_dp_dump_lines(text)
    elif fmt == "rockchip":
        entries = parse_log_lines(text)
    else:
        entries = parse_log_lines(text)
        drm_entries = parse_drm_dp_dump_lines(text)
        if drm_entries and len(drm_entries) > len(entries):
            entries = drm_entries

    if not entries:
        print("No DPCD log entries found.", file=sys.stderr)
        sys.exit(1)
    regs_db = load_regs_db()
    packet_groups = group_mst_entries(entries)
    summary = generate_summary(entries, packet_groups)
    key_findings = generate_key_findings(entries, packet_groups)

    print("=" * 60)
    print("LOG SUMMARY")
    print("=" * 60)
    print(summary)
    print()
    print("=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    if key_findings:
        print("\n".join(key_findings))
    else:
        print("No significant findings.")
    print()

    if args.grouped:
        print("=" * 60)
        print("DPCD REGISTER ACCESSES")
        print("=" * 60)
        dpcd_output = parse_dpcd_registers(entries, regs_db)
        print(dpcd_output)
        print("=" * 60)
        print("MST SIDEBAND MESSAGES (grouped)")
        print("=" * 60)
        mst_output = format_mst_messages(packet_groups)
        print(mst_output)
    else:
        print("=" * 60)
        print("SEQUENTIAL LOG ENTRIES (per-entry with decoding)")
        print("=" * 60)
        seq_output = format_sequential_output(entries, packet_groups, regs_db)
        print(seq_output)

if __name__ == "__main__":
    main()
