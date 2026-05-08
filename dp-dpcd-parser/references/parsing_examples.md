# Navigation

This reference was split from the monolithic `dp-mst-dpcd-parser.md` (1586 lines).

Related files:
- `dpcd_registers.md` - DPCD address space and register definitions (lines 1-375)
- `mst_sideband_spec.md` - MST sideband message format and MT types (lines 376-1145)
- `parsing_examples.md` - Parsing examples and quick reference (lines 1146-1586)

## Quick Navigation

- Line 1: Navigation
- Line 12: 7. NAK 错误码速查
- Line 29: 8. CRC 校验算法
- Line 31: 8.1 Sideband_MSG_Header CRC-4
- Line 74: 8.2 Sideband_MSG_Body CRC-8
- Line 122: 9. Log 解析示例
- Line 124: 9.1 示例 1: REMOTE_I2C_READ ACK (单包)
- Line 170: 9.2 示例 2: REMOTE_I2C_READ ACK (多包第一包)
- Line 203: 9.3 示例 3: REMOTE_I2C_READ ACK (多包完整解析 - EDID 读取)
- Line 403: 10. 快速参考表
- Line 405: 10.1 DPCD 关键地址
- Line 418: 10.2 Message Transaction 标识符
- Line 441: 11. 驱动代码位置

---

## 7. NAK 错误码速查

| Reason_For_Nak | 名称 | 适用场景 |
|:--------------|:-----|:---------|
| 0x01 | WRITE_FAILURE | 所有请求：缓冲区满 |
| 0x02 | INVALID_RAD | 所有请求：地址无效 |
| 0x03 | CRC_FAILURE | 所有请求：CRC 校验失败 |
| 0x04 | BAD_PARAM | 所有请求：参数无效 |
| 0x05 | DEFER | 所有请求：处理超时 |
| 0x06 | LINK_FAILURE | ENUM_PATH_RESOURCES, ALLOCATE_PAYLOAD：链路未建立 |
| 0x07 | NO_RESOURCES | ALLOCATE_PAYLOAD：PBN 不足 |
| 0x08 | DPCD_FAIL | REMOTE_DPCD_READ/WRITE：DPCD 访问失败 |
| 0x09 | I2C_NAK | REMOTE_I2C_READ/WRITE：I2C NAK |
| 0x0A | ALLOCATE_FAIL | ALLOCATE_PAYLOAD：分配失败（非资源不足） |

---

## 8. CRC 校验算法

### 8.1 Sideband_MSG_Header CRC-4

多项式: x⁴ + x + 1

```c
uint8_t drm_dp_msg_header_crc4(const uint8_t *data, size_t num_nibbles)
{
    uint8_t bitmask = 0x80;
    uint8_t bitshift = 7;
    uint8_t array_index = 0;
    int number_of_bits = num_nibbles * 4;
    uint8_t remainder = 0;

    while (number_of_bits != 0) {
        number_of_bits--;
        remainder <<= 1;
        remainder |= (data[array_index] & bitmask) >> bitshift;
        bitmask >>= 1;
        bitshift--;
        if (bitmask == 0) {
            bitmask = 0x80;
            bitshift = 7;
            array_index++;
        }
        if ((remainder & 0x10) == 0x10)
            remainder ^= 0x13;
    }

    number_of_bits = 4;
    while (number_of_bits != 0) {
        number_of_bits--;
        remainder <<= 1;
        if ((remainder & 0x10) != 0)
            remainder ^= 0x13;
    }

    return remainder;
}
```

**校验范围**: 从 LCT 到 MSN 字段（不包括 CRC-4 本身）
**计算 nibble 数**: `(header_length * 2) - 1`

### 8.2 Sideband_MSG_Body CRC-8

多项式: x⁸ + x⁷ + x⁶ + x⁴ + x² + 1 (0xD5)

```c
uint8_t drm_dp_msg_data_crc4(const uint8_t *data, uint8_t number_of_bytes)
{
    uint8_t bitmask = 0x80;
    uint8_t bitshift = 7;
    uint8_t array_index = 0;
    uint16_t number_of_bits = number_of_bytes * 8;
    uint16_t remainder = 0;

    while (number_of_bits != 0) {
        number_of_bits--;
        remainder <<= 1;
        remainder |= (data[array_index] & bitmask) >> bitshift;
        bitmask >>= 1;
        bitshift--;
        if (bitmask == 0) {
            bitmask = 0x80;
            bitshift = 7;
            array_index++;
        }
        if ((remainder & 0x100) == 0x100)
            remainder ^= 0xD5;
    }

    number_of_bits = 8;
    while (number_of_bits != 0) {
        number_of_bits--;
        remainder <<= 1;
        if ((remainder & 0x100) != 0)
            remainder ^= 0xD5;
    }

    return remainder & 0xFF;
}
```

**校验范围**: Body 中所有数据字节（不含 CRC-8 字节本身）
**计算字节数**: `Body_Length - 1`

---


---

## 9. Log 解析示例

### 9.1 示例 1: REMOTE_I2C_READ ACK (单包)

**原始 Log**:
```
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 00 6d d8 5d c4 01 78 80 70 00 30 f0 00
```

**解析步骤**:

**Step 1: 识别缓冲区**
- DPCD 地址 `0x01400` = DOWN_REP (下行回复缓冲区)

**Step 2: 解析 Header (3 字节)**
```
Byte 0: 0x10 = 0b0001_0000
  LCT = 1, LCR = 0 → 直连设备

Byte 1: 0x21 = 0b0010_0001
  Broadcast = 0, Path = 0, Body_Length = 33

Byte 2: 0x0e = 0b0000_1110
  SMT=0, EMT=0, MSN=1, Header_CRC=0xe
```

**Step 3: 解析 Body**
```
Body Length = 33 → 数据 32 字节 + CRC-8 1 字节

数据: 00 6d d8 5d c4 01 78 80 70 00 30 f0 00 78 3f e3
      0f 07 00 e2 00 6a e3 05 c0 00 00 00 00 00 00 00
CRC-8: 0x0f (第 33 字节)
```

**Step 4: 解析 Message Transaction**
```
Byte 0: 0x00 = 0b0_0000000
  Reply_Type = 0 (ACK)
  Request_Identifier = 0x00 (GET_MESSAGE_TRANSACTION_VERSION)

Byte 1: 0x6d = Message_Transaction_Version_Number = 0x6d (异常值)
```

**结论**: 这是一个 GET_MESSAGE_TRANSACTION_VERSION 的 ACK 回复，但版本号 0x6d 异常（应为 0x01 或 0x02）。

---

### 9.2 示例 2: REMOTE_I2C_READ ACK (多包第一包)

**原始 Log**:
```
10 24 87 22 03 80 02 03 3a 60 23 09 07 07 83 01 00 00 46 01 61 01 01 01 01 6d 03 0c 00 00 00 00 44 00 00 00 00 00 80
```

**解析**:

**Header (3 字节)**:
```
Byte 0: 0x10 → LCT=1, LCR=0
Byte 1: 0x24 → Broadcast=0, Path=0, Body_Length=36
Byte 2: 0x87 → SMT=1, EMT=0, MSN=0, Header_CRC=7
```

**Body (36 字节)**:
```
Byte 0: 0x22 → Reply_Type=0 (ACK), Request_ID=0x22 (REMOTE_I2C_READ)
Byte 1: 0x03 → Port_Number = 3
Byte 2: 0x80 → Number_Of_Bytes_Read = 128

Data_Read[0..31]: 02 03 3a 60 23 09 07 07 83 01 00 00 46 01 61 01
                  01 01 01 6d 03 0c 00 00 00 00 44 00 00 00 00 00
CRC-8: 0x80 (第 36 字节)

剩余 96 字节在后续包中
```

**结论**: REMOTE_I2C_READ ACK，从 Port 3 读取 128 字节 I2C 数据（EDID），这是多包消息的第一包。

---

### 9.3 示例 3: REMOTE_I2C_READ ACK (多包完整解析 - EDID 读取)

这是一个完整的 **REMOTE_I2C_READ** 多包消息事务案例，从 Port 3 读取 256 字节 EDID 数据，分为 4 个 Sideband MSG 包传输。

#### 第一包 (Start of Message)

**原始 Log**:
```
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 24 87 22 03 80 00 ff ff ff ff ff ff 00 32 8d
27e40000.dp: 0x01410 AUX -> (ret= 16) 02 2c 01 01 01 01 01 15 01 03 80 59 32 78 0a 0d
27e40000.dp: 0x01420 AUX -> (ret=  7) c9 a0 57 47 98 27 6f
```

**Sideband MSG Header 解析** (3 字节):
```
Byte 0: 0x10 → LCT=1, LCR=0 (直连设备)
Byte 1: 0x24 → Broadcast=0, Path=0, Body_Length=36
Byte 2: 0x87 → SMT=1, EMT=0, MSN=0, Header_CRC=7
```
- **SMT=1, EMT=0**: 这是多包消息的**起始包**
- **Body_Length=36**: 本包携带 36 字节 Body（35 字节数据 + 1 字节 CRC-8）

**Message Transaction 解析**:
```
Byte 0: 0x22 → Reply_Type=0 (ACK), Request_ID=0x22 (REMOTE_I2C_READ)
Byte 1: 0x03 → Port_Number = 3
Byte 2: 0x80 → Number_Of_Bytes_Read = 128 (0x80)

EDID Data[0..32]:
  00 ff ff ff ff ff ff 00  ← EDID Header (0-7 字节)
  32 8d 02 2c 01 01 01 01  ← Vendor/Product ID (8-15 字节)
  01 15 01 03 80 59 32 78  ← Video Input Definition (16-23 字节)
  0a 0d c9 a0 57 47 98 27  ← Color Characteristics (24-31 字节)
  6f                        ← Established Timings (32 字节)

CRC-8: 第 36 字节 (待验证)
```

**本包有效数据**: 35 字节 (Message Transaction Header 3 字节 + EDID Data 32 字节)

---

#### 第二包 (Middle Packet)

**原始 Log**:
```
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 12 48 4c 20 00 00 01 01 01 01 01 01 01
27e40000.dp: 0x01410 AUX -> (ret= 16) 01 01 01 01 01 01 01 01 01 08 e8 00 30 f2 70 5a
27e40000.dp: 0x01420 AUX -> (ret=  4) 80 b0 58 f6
```

**Sideband MSG Header 解析** (3 字节):
```
Byte 0: 0x10 → LCT=1, LCR=0
Byte 1: 0x21 → Broadcast=0, Path=0, Body_Length=33
Byte 2: 0x0e → SMT=0, EMT=0, MSN=1, Header_CRC=0xe
```
- **SMT=0, EMT=0**: 这是**中间包**（非起始也非结束）
- **MSN=1**: 消息序号变为 1（与第一包不同，表示新的 Sideband MSG 事务）
- **Body_Length=33**: 本包携带 33 字节 Body

**Message Transaction 解析**:
```
Byte 0: 0x12 → 这里看起来是新的 Message Transaction 开始？
  → 实际上这是 EDID 数据的延续，不是新的 MT

EDID Data[33..64]:
  48 4c 20 00 00 01 01 01  ← Timing Descriptors (33-40 字节)
  01 01 01 01 01 01 01 01  ← (41-48 字节)
  01 01 01 01 01 01 01 01  ← (49-56 字节)
  01 08 e8 00 30 f2 70 5a  ← (57-64 字节)

CRC-8: 0xf6 (第 33 字节)
```

**注意**: 第二包的第一个字节 `0x12` 看起来像 QUERY_PAYLOAD 的 Request_ID，但结合上下文，这应该是 EDID 数据的延续。实际解析时需要根据 SMT/EMT 标志判断。

---

#### 第三包 (Middle Packet)

**原始 Log**:
```
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 0e 8a 00 55 50 21 00 00 1e 00 00 00 00 00
27e40000.dp: 0x01410 AUX -> (ret= 16) 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
27e40000.dp: 0x01420 AUX -> (ret=  4) fd 00 32 25
```

**Sideband MSG Header 解析**:
```
Byte 0: 0x10 → LCT=1, LCR=0
Byte 1: 0x21 → Body_Length=33
Byte 2: 0x0e → SMT=0, EMT=0, MSN=1
```
- **SMT=0, EMT=0**: 仍是**中间包**
- **MSN=1**: 与第二包相同

**EDID Data[65..96]**:
```
8a 00 55 50 21 00 00 1e 00 00 00 00 00 00 00 00  ← (65-80 字节)
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ← (81-96 字节)

CRC-8: 0x25 (第 33 字节)
```

---

#### 第四包 (End of Message)

**原始 Log**:
```
27e40000.dp: 0x01400 AUX -> (ret= 16) 10 21 42 3c 1e 46 0f 01 0a 20 20 20 20 20 20 00
27e40000.dp: 0x01410 AUX -> (ret= 16) 00 00 fc 00 4c 43 44 0a 20 20 20 20 20 20 20 20
27e40000.dp: 0x01420 AUX -> (ret=  4) 20 01 50 24
```

**Sideband MSG Header 解析**:
```
Byte 0: 0x10 → LCT=1, LCR=0
Byte 1: 0x42 → Body_Length=66 (0x42 = 66)
Byte 2: 0x3c → SMT=0, EMT=1, MSN=1, Header_CRC=0xc
```
- **SMT=0, EMT=1**: 这是**结束包**
- **Body_Length=66**: 本包携带 66 字节 Body（65 字节数据 + 1 字节 CRC-8）

**EDID Data[97..127] + Monitor Descriptor**:
```
3c 1e 46 0f 01 0a 20 20 20 20 20 20 00 00 00 fc  ← (97-112 字节)
00 4c 43 44 0a 20 20 20 20 20 20 20 20 20 01 50  ← (113-127 字节)
24                                               ← CRC-8

Monitor Descriptor (ASCII): "LCD" (从 0xFC 开始)
```

---

#### 完整 Message Transaction 重组

**4 个包拼接后的完整数据**:

| 包序号 | SMT/EMT | Body_Length | 数据字节 | 累计字节 |
|:------:|:-------:|:-----------:|:--------:|:--------:|
| 1 | 1/0 | 36 | 35 | 35 |
| 2 | 0/0 | 33 | 32 | 67 |
| 3 | 0/0 | 33 | 32 | 99 |
| 4 | 0/1 | 66 | 65 | 164 |

**完整 Message Transaction** (164 字节):
```
Byte 0-2:   22 03 80        ← MT Header (REMOTE_I2C_READ ACK, Port 3, 128 bytes)
Byte 3-130: EDID Data[0..127] (128 字节)
Byte 131+:   其他填充/描述符数据
```

**EDID 完整数据** (128 字节标准 EDID + 扩展):
```
00 ff ff ff ff ff ff 00 32 8d 02 2c 01 01 01 01  ← 000-015
01 15 01 03 80 59 32 78 0a 0d c9 a0 57 47 98 27  ← 016-031
6f 48 4c 20 00 00 01 01 01 01 01 01 01 01 01 01  ← 032-047
01 01 01 01 01 01 01 01 01 08 e8 00 30 f2 70 5a  ← 048-063
8a 00 55 50 21 00 00 1e 00 00 00 00 00 00 00 00  ← 064-079
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ← 080-095
3c 1e 46 0f 01 0a 20 20 20 20 20 20 00 00 00 fc  ← 096-111
00 4c 43 44 0a 20 20 20 20 20 20 20 20 20 01 50  ← 112-127
24                                               ← 128 (CRC)
```

**解析关键点**:

1. **SMT/EMT 标志组合**:
   - `SMT=1, EMT=0`: 第一包
   - `SMT=0, EMT=0`: 中间包
   - `SMT=0, EMT=1`: 最后一包
   - `SMT=1, EMT=1`: 单包完成

2. **MSN (Message Sequence No)**:
   - 用于区分并发的两个 Message Transaction
   - 同一 MT 的所有包 MSN 相同

3. **Body_Length 变化**:
   - 每包 Body_Length 可能不同
   - 实际数据 = Body_Length - 1 (减去 CRC-8)

4. **Message Transaction 重组**:
   - 拼接所有包的 `Body[0..Body_Length-2]`
   - 跳过每个包的最后一个字节 (CRC-8)
   - 第一个字节是 MT Header (Reply_Type + Request_Identifier)

5. **REMOTE_I2C_READ ACK 结构**:
   ```
   Byte 0: Reply_Type(1) + Request_ID(7) = 0x22 (ACK + REMOTE_I2C_READ)
   Byte 1: Port_Number (4) + zeros (4) = 0x03 (Port 3)
   Byte 2: Number_Of_Bytes_Read = 0x80 (128 字节)
   Byte 3+: I2C_Data_Read[0..127] (128 字节 EDID)
   ```

---



## 10. 快速参考表

### 10.1 DPCD 关键地址

| 地址 | 名称 | 访问 | 说明 |
|:-----|:-----|:-----|:-----|
| 0x00021 | MSTM_CAP | RO | MST 能力 |
| 0x00111 | MSTM_CTRL | RW | MST 控制 |
| 0x00201 | DEVICE_SERVICE_IRQ_VECTOR | RW1C | 中断向量 |
| 0x01000-0x011FF | DOWN_REQ | WO | 下行请求缓冲 |
| 0x01200-0x013FF | UP_REP | WO | 上行回复缓冲 |
| 0x01400-0x015FF | DOWN_REP | RO | 下行回复缓冲 |
| 0x01600-0x017FF | UP_REQ | RO | 上行请求缓冲 |
| 0x02003 | DEVICE_SERVICE_IRQ_VECTOR_ESI0 | RW1C | ESI 中断 |

### 10.2 Message Transaction 标识符

| ID | 名称 | 方向 | 类型 | 最小长度 |
|:---|:-----|:-----|:-----|:---------|
| 0x00 | GET_MSG_VERSION | DOWN | 节点 | 2B |
| 0x01 | LINK_ADDRESS | DOWN | 节点 | 1B |
| 0x02 | CONNECTION_STATUS | UP | 广播 | 20B |
| 0x10 | ENUM_PATH | DOWN | 路径 | 2B |
| 0x11 | ALLOCATE | DOWN | 路径/节点 | 6B+ |
| 0x12 | QUERY_PAYLOAD | DOWN | 节点 | 3B |
| 0x13 | RESOURCE_STATUS | UP | 广播 | 21B |
| 0x14 | CLEAR_PAYLOAD | DOWN | 广播 | 1B |
| 0x20 | REMOTE_DPCD_READ | DOWN | 节点 | 5B |
| 0x21 | REMOTE_DPCD_WRITE | DOWN | 节点 | 5B+ |
| 0x22 | REMOTE_I2C_READ | DOWN | 节点 | 4B+ |
| 0x23 | REMOTE_I2C_WRITE | DOWN | 节点 | 4B+ |
| 0x24 | POWER_UP_PHY | DOWN | 路径/节点 | 2B |
| 0x25 | POWER_DOWN_PHY | DOWN | 路径/节点 | 2B |
| 0x30 | SINK_EVENT | UP | 广播 | TBD |
| 0x38 | QUERY_STREAM_ENC | DOWN | 节点 | 11B |

---

## 11. 驱动代码位置

| 功能 | 文件路径 |
|:-----|:---------|
| DPCD 寄存器定义 | `include/drm/display/drm_dp.h` |
| MST 拓扑管理 | `drivers/gpu/drm/display/drm_dp_mst_topology.c` |
| Rockchip MST 辅助 | `drivers/gpu/drm/rockchip/rockchip_dp_mst_aux_client_helper.c` |
| DW-DP 驱动 | `drivers/gpu/drm/rockchip/dw-dp.c` |
| CDN-DP 寄存器定义 | `drivers/gpu/drm/rockchip/cdn-dp-reg.h` (AUX_STATUS_ACK/NACK/DEFER) |

