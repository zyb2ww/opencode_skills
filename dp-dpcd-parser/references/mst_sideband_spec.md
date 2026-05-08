# Navigation

This reference was split from the monolithic `dp-mst-dpcd-parser.md` (1586 lines).

Related files:
- `dpcd_registers.md` - DPCD address space and register definitions (lines 1-375)
- `mst_sideband_spec.md` - MST sideband message format and MT types (lines 376-1145)
- `parsing_examples.md` - Parsing examples and quick reference (lines 1146-1586)

## Quick Navigation

- Line 1: Navigation
- Line 10: 2.1 缓冲区地址映射 (Table 2-169)
- Line 27: 2.2 缓冲区大小和传输限制
- Line 33: 2.3 消息传递流程
- Line 48: 2. MST Sideband MSG 缓冲区
- Line 53: 3. MST 关键控制寄存器
- Line 55: 3.1 MSTM_CAP (DPCD 0x00021)
- Line 64: 3.2 MSTM_CTRL (DPCD 0x00111)
- Line 75: 3.3 DEVICE_SERVICE_IRQ_VECTOR (DPCD 0x00201 / 0x02003)
- Line 94: 4. Sideband MSG Layer 语法
- Line 96: 4.1 Sideband_MSG 结构 (Table 2-189)
- Line 105: 4.2 Sideband_MSG_Header 语法 (Table 2-190)
- Line 154: 4.3 Sideband_MSG_Body 语法 (Table 2-191)
- Line 176: 5. Message Transaction Layer 语法
- Line 178: 5.1 Message_Transaction_Sequence (Table 2-181)
- Line 187: 5.2 Message_Transaction_Request (Table 2-182)
- Line 197: 5.3 Request_Identifier 列表 (Table 2-183)
- Line 218: 5.4 Message_Transaction_Reply (Table 2-185)
- Line 228: 5.5 Reply_Data 语法 (Table 2-186)
- Line 242: 5.6 NAK 原因码 (Table 2-187)
- Line 257: 5.7 Reply_Type 快速解析
- Line 269: 6. 14 种 Message Transaction 详解
- Line 271: 6.1 GET_MESSAGE_TRANSACTION_VERSION (0x00)
- Line 301: 6.2 LINK_ADDRESS (0x01)
- Line 361: 6.3 CONNECTION_STATUS_NOTIFY (0x02)
- Line 392: 6.4 ENUM_PATH_RESOURCES (0x10)
- Line 421: 6.5 ALLOCATE_PAYLOAD (0x11)
- Line 458: 6.6 QUERY_PAYLOAD (0x12)
- Line 486: 6.7 RESOURCE_STATUS_NOTIFY (0x13)
- Line 512: 6.8 CLEAR_PAYLOAD_ID_TABLE (0x14)

### 2.1 缓冲区地址映射 (Table 2-169)

| 缓冲区名称 | DPCD 地址范围 | 访问权限 | 说明 |
|:----------|:-------------|:--------|:-----|
| **DOWN_REQ** | `0x1000 - 0x11FF` | Write/Read | 下行请求缓冲区（Source 写，Branch/Sink 读） |
| **UP_REP** | `0x1200 - 0x13FF` | Write/Read | 上行回复缓冲区（Source 写，Branch/Sink 读） |
| **DOWN_REP** | `0x1400 - 0x15FF` | Read Only | 下行回复缓冲区（Branch/Sink 写，Source 读） |
| **UP_REQ** | `0x1600 - 0x17FF` | Read Only | 上行请求缓冲区（Branch/Sink 写，Source 读） |

**驱动代码定义** (`include/drm/display/drm_dp.h`):
```c
#define DP_SIDEBAND_MSG_DOWN_REQ_BASE   0x1000   /* DP 1.2 MST */
#define DP_SIDEBAND_MSG_UP_REP_BASE     0x1200   /* DP 1.2 MST */
#define DP_SIDEBAND_MSG_DOWN_REP_BASE   0x1400   /* DP 1.2 MST */
#define DP_SIDEBAND_MSG_UP_REQ_BASE     0x1600   /* DP 1.2 MST */
```

### 2.2 缓冲区大小和传输限制

- 每个缓冲区大小：**512 字节** (`0x200` bytes)
- 单个 Sideband MSG 最大长度：**48 字节**（含 Header 和 CRC）
- 多包消息：当 Message Transaction 超过 48 字节时，需分多个 Sideband MSG 传输

### 2.3 消息传递流程

**DOWN_REQ_MSG (下行请求)**:
```
Source (DPTX) → 写入 DOWN_REQ → 触发 IRQ_HPD → Branch/Sink 读取并执行 → 写入 DOWN_REP → 触发 IRQ_HPD → Source 读取
```

**UP_REQ_MSG (上行请求)**:
```
Branch/Sink (DPRX) → 写入 UP_REQ → 触发 IRQ_HPD → Source 读取并执行 → 写入 UP_REP → 触发 IRQ_HPD → Branch/Sink 读取
```


---

## 2. MST Sideband MSG 缓冲区


---

## 3. MST 关键控制寄存器

### 3.1 MSTM_CAP (DPCD 0x00021)

| Bit | 名称 | 值 | 含义 |
|:----|:-----|:---|:-----|
| 0 | MST_CAP | 0 | 不支持 MST |
|  |  | 1 | 支持 MST 框架 |
| 1 | SINGLE_STREAM_SIDEBAND_MSG | 0 | 不支持单流 sideband (DP 2.0) |
|  |  | 1 | 支持单流 sideband |

### 3.2 MSTM_CTRL (DPCD 0x00111)

| Bit | 名称 | 值 | 含义 |
|:----|:-----|:---|:-----|
| 0 | MST_EN | 0 | 禁用 MST |
|  |  | 1 | 启用 MST |
| 1 | UP_REQ_EN | 0 | 不接受 UP Sideband MSG |
|  |  | 1 | 接受并回复 UP 请求 |
| 2 | UPSTREAM_IS_SRC | 0 | 上游不是 Source |
|  |  | 1 | 上游是 Source |

### 3.3 DEVICE_SERVICE_IRQ_VECTOR (DPCD 0x00201 / 0x02003)

| Bit | 名称 | 含义 |
|:----|:-----|:-----|
| 0 | REMOTE_CONTROL_CMD_PENDING | 远程控制命令挂起 |
| 1 | AUTOMATED_TEST_REQUEST | 自动测试请求 |
| 2 | CP_IRQ | 内容保护中断 |
| 3 | MCCS_IRQ | MCCS 中断 |
| 4 | DOWN_REP_MSG_RDY | **DOWN_REP 消息就绪** |
| 5 | UP_REQ_MSG_RDY | **UP_REQ 消息就绪** |
| 6 | SINK_SPECIFIC_IRQ | Sink 特定中断 |

> **关键**: 当 Source 收到 IRQ_HPD 时，应检查 bit[4] 和 bit[5] 判断是否有 Sideband 消息待读取。

---


---

## 4. Sideband MSG Layer 语法

### 4.1 Sideband_MSG 结构 (Table 2-189)

```
Sideband_MSG {
    Sideband_MSG_Header()    // 变长，3-7 字节
    Sideband_MSG_Body()      // 变长，1-45 字节
}
```

### 4.2 Sideband_MSG_Header 语法 (Table 2-190)

```c
Sideband_MSG_Header() {
    // Byte 0
    Link_Count_Total          [4 bits]   // LCT: 消息经过的总链路数 (1-15)
    Link_Count_Remaining      [4 bits]   // LCR: 剩余链路数
    
    // Byte 1 to (LCT-1)/2
    for (i = 0; i < LCT - 1; i++)
        Relative_Address[i]   [4 bits]   // RAD: 相对地址 (每个 nibble 是一个端口号)
    
    // 字节对齐填充 (仅当 LCT-1 为奇数时)
    while (!bytealigned())
        zero_bit              [1 bit]
    
    // 地址后第一个完整字节
    Broadcast_Message         [1 bit]    // 0=单播，1=广播
    Path_Message              [1 bit]    // 0=节点消息，1=路径消息
    Sideband_MSG_Body_Length  [6 bits]   // Body 长度（含 CRC-8），实际数据 = Length-1
    
    // 控制字节
    Start_Of_Msg_Transaction  [1 bit]    // SMT: 1=消息起始
    End_Of_Msg_Transaction    [1 bit]    // EMT: 1=消息结束
    zero                      [1 bit]    // 保留位
    Message_Sequence_No       [1 bit]    // MSN: 消息序号 (0/1)
    Sideband_MSG_Header_CRC   [4 bits]   // Header CRC-4
}
```

**Header 长度计算**:
- 最小长度: 3 字节 (LCT=1, 无 RAD)
- 最大长度: 7 字节 (LCT=15, 14 个 RAD nibbles = 7 字节)

**字段详解**:

| 字段 | 位置 | 说明 |
|:-----|:-----|:-----|
| **LCT** | Byte 0[7:4] | 消息从源到目标经过的总链路数。LCT=1 表示直连设备 |
| **LCR** | Byte 0[3:0] | 消息还需经过的链路数。每经过一个 Branch 设备减 1 |
| **RAD[]** | Byte 1+ | 相对地址数组，每个 nibble 代表路径上的一个端口号 |
| **Broadcast** | 地址后字节 [7] | 1=广播消息，发往所有端口 |
| **Path_Message** | 地址后字节 [6] | 1=路径消息，路径上所有设备都处理；0=节点消息，仅目标设备处理 |
| **Body_Length** | 地址后字节 [5:0] | Body 总字节数（含 CRC-8），范围 1-48 |
| **SMT** | 控制字节 [7] | 1=这是 Message Transaction 的第一个 Sideband MSG |
| **EMT** | 控制字节 [6] | 1=这是 Message Transaction 的最后一个 Sideband MSG |
| **MSN** | 控制字节 [4] | 消息序号，用于区分并发的两个消息 |
| **Header_CRC** | 控制字节 [3:0] | CRC-4 校验，多项式 x⁴+x+1 |

### 4.3 Sideband_MSG_Body 语法 (Table 2-191)

```c
Sideband_MSG_Body() {
    // 数据部分
    for (i = 0; i < Sideband_MSG_Body_Length - 1; i++)
        Sideband_MSG_Data     [8 bits]   // 消息数据
    
    // CRC 部分
    Sideband_MSG_Data_CRC     [8 bits]   // Body CRC-8
}
```

**数据长度**:
- 实际数据字节数 = `Body_Length - 1`
- 最后 1 字节固定为 CRC-8

---


---

## 5. Message Transaction Layer 语法

### 5.1 Message_Transaction_Sequence (Table 2-181)

```
Message_Transaction_Sequence {
    Message_Transaction_Request()
    Message_Transaction_Reply()
}
```

### 5.2 Message_Transaction_Request (Table 2-182)

```c
Message_Transaction_Request() {
    zero                  [1 bit]    // 固定为 0
    Request_Identifier    [7 bits]   // 请求标识符（见下表）
    Request_Data()                   // 可选，取决于 Request_Identifier
}
```

### 5.3 Request_Identifier 列表 (Table 2-183)

| ID | 驱动宏定义 | 请求名称 | 有请求数据 | 方向 |
|:---|:----------|:---------|:----------|:-----|
| 0x00 | DP_GET_MSG_TRANSACTION_VERSION | GET_MESSAGE_TRANSACTION_VERSION | 有 | DOWN |
| 0x01 | DP_LINK_ADDRESS | LINK_ADDRESS | 无 | DOWN |
| 0x02 | DP_CONNECTION_STATUS_NOTIFY | CONNECTION_STATUS_NOTIFY | 有 | UP (广播) |
| 0x10 | DP_ENUM_PATH_RESOURCES | ENUM_PATH_RESOURCES | 有 | DOWN (路径) |
| 0x11 | DP_ALLOCATE_PAYLOAD | ALLOCATE_PAYLOAD | 有 | DOWN (路径/节点) |
| 0x12 | DP_QUERY_PAYLOAD | QUERY_PAYLOAD | 有 | DOWN |
| 0x13 | DP_RESOURCE_STATUS_NOTIFY | RESOURCE_STATUS_NOTIFY | 有 | UP (广播) |
| 0x14 | DP_CLEAR_PAYLOAD_ID_TABLE | CLEAR_PAYLOAD_ID_TABLE | 无 | DOWN (广播) |
| 0x20 | DP_REMOTE_DPCD_READ | REMOTE_DPCD_READ | 有 | DOWN |
| 0x21 | DP_REMOTE_DPCD_WRITE | REMOTE_DPCD_WRITE | 有 | DOWN |
| 0x22 | DP_REMOTE_I2C_READ | REMOTE_I2C_READ | 有 | DOWN |
| 0x23 | DP_REMOTE_I2C_WRITE | REMOTE_I2C_WRITE | 有 | DOWN |
| 0x24 | DP_POWER_UP_PHY | POWER_UP_PHY | 有 | DOWN (路径/节点) |
| 0x25 | DP_POWER_DOWN_PHY | POWER_DOWN_PHY | 有 | DOWN (路径/节点) |
| 0x30 | DP_SINK_EVENT_NOTIFY | SINK_EVENT_NOTIFY | 有 | UP (广播) |
| 0x38 | DP_QUERY_STREAM_ENC_STATUS | QUERY_STREAM_ENCRYPTION_STATUS | 有 | DOWN |

### 5.4 Message_Transaction_Reply (Table 2-185)

```c
Message_Transaction_Reply() {
    Reply_Type            [1 bit]    // 0=ACK, 1=NAK
    Request_Identifier    [7 bits]   // 与请求中的 Request_Identifier 相同
    Reply_Data()                     // ACK_Data() 或 NAK_Data()
}
```

### 5.5 Reply_Data 语法 (Table 2-186)

```c
Reply_Data() {
    if (Reply_Type == 1) {    // NAK
        Global_Unique_Identifier  [128 bits]   // 16 字节，NAK 来源设备的 GUID
        Reason_For_Nak            [8 bits]     // NAK 原因码
        NAK_Data                  [8 bits]     // 附加 NAK 信息
    } else {                   // ACK
        ACK_Data()                             // 依 Request_Identifier 而定
    }
}
```

### 5.6 NAK 原因码 (Table 2-187)

| 值 | 驱动宏定义 | 名称 | 描述 |
|:---|:----------|:-----|:-----|
| 0x01 | DP_NAK_WRITE_FAILURE | WRITE_FAILURE | 缓冲区空间不足 |
| 0x02 | DP_NAK_INVALID_READ | INVALID_RAD | 无效地址/向逻辑端口发送 |
| 0x03 | DP_NAK_CRC_FAILURE | CRC_FAILURE | 消息 CRC 错误 |
| 0x04 | DP_NAK_BAD_PARAM | BAD_PARAM | 无效请求参数 |
| 0x05 | DP_NAK_DEFER | DEFER | 超时无法处理 |
| 0x06 | DP_NAK_LINK_FAILURE | LINK_FAILURE | 链路故障 |
| 0x07 | DP_NAK_NO_RESOURCES | NO_RESOURCES | 资源不足 |
| 0x08 | DP_NAK_DPCD_FAIL | DPCD_FAIL | DPCD 访问失败 |
| 0x09 | DP_NAK_I2C_NAK | I2C_NAK | I2C NAK 收到 |
| 0x0A | DP_NAK_ALLOCATE_FAIL | ALLOCATE_FAIL | ALLOCATE_PAYLOAD 失败 |

### 5.7 Reply_Type 快速解析

**字节值解析规则**:
- `byte & 0x80 != 0` → NAK (Reply_Type=1)
- `byte & 0x80 == 0` → ACK (Reply_Type=0)
- `byte & 0x7F` → Request_Identifier

---


---

## 6. 14 种 Message Transaction 详解

### 6.1 GET_MESSAGE_TRANSACTION_VERSION (0x00)

**Request**:
```c
GET_MESSAGE_TRANSACTION_VERSION_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x00
    Port_Number             [4]
    Zeros                   [4]
}
// 总计: 2 字节
```

**ACK Reply**:
```c
GET_MESSAGE_TRANSACTION_VERSION_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x00
    Message_Transaction_Version_Number [8]
}
// 总计: 2 字节
```

| 版本号 | DP 标准 |
|:-------|:--------|
| 0x01 | DP v1.2a (DPCD r1.2) |
| 0x02 | DP v1.3/v1.4a (DPCD r1.4) |

---

### 6.2 LINK_ADDRESS (0x01)

**Request**:
```c
LINK_ADDRESS_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x01
}
// 总计: 1 字节（无请求数据）
```

**ACK Reply**:
```c
LINK_ADDRESS_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x01
    Global_Unique_Identifier [128]  // 16 字节 GUID
    zeros                   [4]
    Number_Of_Ports         [4]
    
    for (i = 0; i < Number_Of_Ports; i++) {
        Input_Port[i]       [1]    // 1=输入端口(DPRX), 0=输出端口(DPTX)
        Peer_Device_Type[i] [3]    // 见 Peer_Device_Type 表
        Port_Number[i]      [4]    // 物理端口 0-7，逻辑端口 8-15
        
        Messaging_Capability_Status[i]  [1]  // MST_CAP + UP_REQ_EN
        DisplayPort_Device_Plug_Status[i] [1] // 设备已连接并初始化
        
        if (Peer_Device_Type[i] == 0b101) {  // DP-to-Wireless
            Current_Capabilities_Structure [128]  // 16 字节 CCS
        }
        
        if (Input_Port[i] == 0) {  // 输出端口
            Legacy_Device_Plug_Status[i] [1]
            zeros                       [5]
            DPCD_Revision               [8]
            Peer_Global_Unique_Identifier [128]  // 16 字节
            Number_SDP_Streams[i]       [4]
            Number_SDP_Stream_Sinks[i]  [4]
        } else {  // 输入端口
            zeros                       [6]
        }
    }
}
```

**Peer_Device_Type 值** (Table 2-195):

| 值 | 设备类型 |
|:---|:---------|
| 0b000 | 无设备连接 |
| 0b001 | MST Source 或 SST-only Source Branch |
| 0b010 | MST Branch 或 SST-only Branch |
| 0b011 | SST Sink (无 Branching Unit) |
| 0b100 | DP-to-Legacy 协议转换器 (VGA/DVI/HDMI) |
| 0b101 | DP-to-Wireless 协议转换器 |
| 0b110 | Wireless-to-DP 协议转换器 |

---

### 6.3 CONNECTION_STATUS_NOTIFY (0x02)

**Request (广播)**:
```c
CONNECTION_STATUS_NOTIFY_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x02
    Port_Number             [4]
    zeros                   [4]
    Global_Unique_Identifier [128]  // 16 字节
    zero                    [1]
    Legacy_Device_Plug_Status [1]
    DisplayPort_Device_Plug_Status [1]
    Messaging_Capability_Status [1]
    Input_Port              [1]
    Peer_Device_Type        [3]
}
// 总计: 20 字节
```

**ACK Reply**:
```c
CONNECTION_STATUS_NOTIFY_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x02
}
// 总计: 1 字节
```

---

### 6.4 ENUM_PATH_RESOURCES (0x10)

**Request (路径消息)**:
```c
ENUM_PATH_RESOURCES_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x10
    Port_Number             [4]
    zeros                   [4]
}
// 总计: 2 字节
```

**ACK Reply**:
```c
ENUM_PATH_RESOURCES_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x10
    Port_Number             [4]
    zeros                   [3]
    FEC_Capability          [1]    // 1=路径支持 FEC
    Full_Payload_Bandwidth_Number    [16]
    Available_Payload_Bandwidth_Number [16]
}
// 总计: 7 字节
```

---

### 6.5 ALLOCATE_PAYLOAD (0x11)

**Request (路径/节点消息)**:
```c
ALLOCATE_PAYLOAD_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x11
    Port_Number             [4]
    Number_SDP_Streams      [4]
    zero                    [1]    // '0'
    Virtual_Channel_Payload_Identifier [7]
    Payload_Bandwidth_Number [16]
    for (i = 0; i < Number_SDP_Streams; i++) {
        SDP_Stream_Sink[i]  [4]
    }
    while (!bytealigned()) {
        zero                [1]
    }
}
// 最少 6 字节 (Number_SDP_Streams=0)
```

**ACK Reply**:
```c
ALLOCATE_PAYLOAD_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x11
    Port_Number             [4]
    zeros                   [5]
    Virtual_Channel_Payload_Identifier [7]
    Allocated_Payload_Bandwidth_Number [16]
}
// 总计: 5 字节
```

---

### 6.6 QUERY_PAYLOAD (0x12)

**Request**:
```c
QUERY_PAYLOAD_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x12
    Port_Number             [4]
    zeros                   [5]
    Virtual_Channel_Payload_Identifier [7]
}
// 总计: 3 字节
```

**ACK Reply**:
```c
QUERY_PAYLOAD_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x12
    Port_Number             [4]
    zeros                   [4]
    Allocated_PBN           [16]
}
// 总计: 4 字节
```

---

### 6.7 RESOURCE_STATUS_NOTIFY (0x13)

**Request (广播)**:
```c
RESOURCE_STATUS_NOTIFY_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x13
    Port_Number             [4]
    zeros                   [4]
    Global_Unique_Identifier [128]  // 16 字节
    Available_PBN           [16]
}
// 总计: 21 字节
```

**ACK Reply**:
```c
RESOURCE_STATUS_NOTIFY_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x13
}
// 总计: 1 字节
```

---

### 6.8 CLEAR_PAYLOAD_ID_TABLE (0x14)

**Request (广播)**:
```c
CLEAR_PAYLOAD_ID_TABLE_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x14
}
// 总计: 1 字节（无请求数据）
```

**ACK Reply**:
```c
CLEAR_PAYLOAD_ID_TABLE_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x14
}
// 总计: 1 字节
```

---

### 6.9 REMOTE_DPCD_READ (0x20)

**Request**:
```c
REMOTE_DPCD_READ_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x20
    Port_Number             [4]
    DPCD_Address            [20]   // 20-bit DPCD 地址
    Number_Of_Bytes_To_Read [8]
}
// 总计: 5 字节
```

**ACK Reply**:
```c
REMOTE_DPCD_READ_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x20
    zeros                   [4]
    Port_Number             [4]
    Number_Of_Bytes_Read    [8]
    for (i = 0; i < Number_Of_Bytes_Read; i++) {
        DPCD_Byte_Read[i]   [8]
    }
}
// 最少 4 字节 (0 bytes read)
```

---

### 6.10 REMOTE_DPCD_WRITE (0x21)

**Request**:
```c
REMOTE_DPCD_WRITE_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x21
    Port_Number             [4]
    DPCD_Address            [20]
    Number_Of_Bytes_To_Write [8]
    for (i = 0; i < Number_Of_Bytes_To_Write; i++) {
        DPCD_Byte_To_Write[i] [8]
    }
}
// 最少 5 字节 (0 bytes to write)
```

**ACK Reply**:
```c
REMOTE_DPCD_WRITE_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x21
    zeros                   [4]
    Port_Number             [4]
}
// 总计: 2 字节
```

**NAK Reply**:
```c
REMOTE_DPCD_WRITE_Nak_Reply() {
    Reply_Type              [1]    // '1' (NAK)
    Request_Identifier      [7]    // 0x21
    Global_Unique_Identifier [128]  // 16 字节
    Reason_For_Nak          [8]
    Number_Of_Bytes_Written_Before_Failure [8]
}
// 总计: 20 字节
```

---

### 6.11 REMOTE_I2C_READ (0x22)

**Request**:
```c
REMOTE_I2C_READ_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x22
    Port_Number             [4]
    zeros                   [2]
    Number_Of_I2C_Transactions [2]  // 1-3
    
    // 前面的写事务 (Number_Of_I2C_Transactions - 1 个)
    for (i = 0; i < Number_Of_I2C_Transactions - 1; i++) {
        zero                [1]
        Write_I2C_Device_Identifier[i] [7]
        Number_Of_Bytes_To_Write[i]    [8]
        for (j = 0; j < Number_Of_Bytes_To_Write; j++) {
            I2C_Data_To_Write[i][j]    [8]
        }
        zeros               [3]
        No_Stop_Bit[i]      [1]
        I2C_Transaction_Delay[i] [4]
    }
    
    // 最后的读事务
    zero                    [1]
    Read_I2C_Device_Identifier [7]
    Number_Of_Bytes_To_Read [8]
}
```

**ACK Reply**:
```c
REMOTE_I2C_READ_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x22
    zeros                   [4]
    Port_Number             [4]
    Number_Of_Bytes_Read    [8]
    for (i = 0; i < Number_Of_Bytes_Read; i++) {
        I2C_Device_Byte_Read[i] [8]
    }
}
// 最少 4 字节 (0 bytes read)
```

**NAK Reply (I2C 专用)**:
```c
REMOTE_I2C_READ_Nak_Reply() {
    Reply_Type              [1]    // '1' (NAK)
    Request_Identifier      [7]    // 0x22
    Global_Unique_Identifier [128]  // 16 字节
    Reason_For_Nak          [8]
    NAK_Data: {
        I2C_NAK_Transaction [8]    // NAK 发生在第几个 I2C 事务 (1-3)
    }
}
```

---

### 6.12 REMOTE_I2C_WRITE (0x23)

**Request**:
```c
REMOTE_I2C_WRITE_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x23
    Port_Number             [4]
    zeros                   [5]
    Write_I2C_Device_Identifier [7]
    Number_Of_Bytes_To_Write [8]
    for (i = 0; i < Number_Of_Bytes_To_Write; i++) {
        I2C_Data_To_Write[i] [8]
    }
}
// 最少 4 字节 (0 bytes to write)
```

**ACK Reply**:
```c
REMOTE_I2C_WRITE_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x23
    zeros                   [4]
    Port_Number             [4]
}
// 总计: 2 字节
```

---

### 6.13 POWER_UP_PHY (0x24) / POWER_DOWN_PHY (0x25)

**Request**:
```c
POWER_UP_PHY_Request() / POWER_DOWN_PHY_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x24 / 0x25
    Port_Number             [4]
    zeros                   [4]
}
// 总计: 2 字节
```

**ACK Reply** (两者格式相同):
```c
POWER_UP_PHY_Ack_Reply() / POWER_DOWN_PHY_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x24 / 0x25
    Port_Number             [4]
    zeros                   [4]
}
// 总计: 2 字节
```

---

### 6.14 SINK_EVENT_NOTIFY (0x30)

**Request (广播, 上行)**:
```c
SINK_EVENT_NOTIFY_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x30
    // TBD in future version
}
```

---

### 6.15 QUERY_STREAM_ENCRYPTION_STATUS (0x38)

**Request**:
```c
QUERY_STREAM_ENCRYPTION_STATUS_Request() {
    zero                    [1]    // '0'
    Request_Identifier      [7]    // 0x38
    Stream_ID               [8]
    Client_ID               [56]   // 7 字节
    Stream_Event            [2]
    Stream_Event_Mask       [1]
    Stream_Behavior         [2]
    Stream_Behavior_Mask    [1]
    zeros                   [2]
}
// 总计: 11 字节
```

**ACK Reply**:
```c
QUERY_STREAM_ENCRYPTION_STATUS_Ack_Reply() {
    Reply_Type              [1]    // '0' (ACK)
    Request_Identifier      [7]    // 0x38
    Stream_State            [2]    // 0=不存在, 1=未激活, 2=激活
    Stream_Repeater_Function [1]
    Stream_Encryption       [1]
    Stream_Authentication   [1]
    Zeros                   [3]
    Stream_output_sink_type [3]
    Stream_Output_CP_Type   [2]
    Zeros                   [2]
    Signed                  [1]
    Stream_ID               [8]
    if (Signed == 1) {
        L'                  [160 or 256]  // 签名数据
    }
}
```

---


