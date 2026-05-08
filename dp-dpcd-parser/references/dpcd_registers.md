# DPCD Registers Reference (DP 2.1 + eDP 1.5)

本文档基于 **DP 2.1 规范** (DP-2.1-specification.pdf) 和 **eDP 1.5 规范** (eDP-1.5-specification.pdf)，涵盖 DP 2.1 和 eDP 1.5 新增的 DPCD 寄存器定义。

---

## Quick Navigation

- **DP 2.1 新增**: 128b/132b 编码, UHBR10/13.5/20, AUX-LDPS, FEC, DSC 2.0, LTTPR
- **eDP 1.5 新增**: ALPM, PSR2, Panel Replay, VESA DSC, 帧率匹配

---

## 1. DPCD 地址空间总览 (DP 2.1 Section 2.9.3)

| DPCD 地址范围 | 功能区域 | DP 2.1 更新 |
|:-------------|:---------|:------------|
| `0x00000 - 0x000FF` | Receiver Capability | ✅ 新增 128b/132b, UHBR rates |
| `0x00100 - 0x001FF` | Link Configuration | ✅ 新增 UHBR 配置，FEC 配置 |
| `0x00200 - 0x002FF` | Link/Sink Status | ✅ 新增 128b/132b EQ 状态 |
| `0x00300 - 0x003FF` | Source Device-specific | — |
| `0x00400 - 0x004FF` | Sink Device-specific | — |
| `0x00500 - 0x005FF` | Branch Device-specific | — |
| `0x00600 - 0x006FF` | Power Control | — |
| `0x00700 - 0x007FF` | eDP-specific | ✅ eDP 1.5 ALPM/PSR2 |
| `0x00800 - 0x008FF` | Link/Sink Status (Alt) | ✅ DP 2.1 新增 |
| `0x01000 - 0x017FF` | Sideband MSG Buffers | — |
| `0x02000 - 0x021FF` | ESI | — |
| `0x02200 - 0x022FF` | Extended Receiver Cap | ✅ DP 2.1 UHBR/128b132b 能力 |
| `0x03000 - 0x030FF` | Protocol Converter | — |
| `0x04000 - 0x04FFF` | FEC Extended | ✅ DP 2.1 新增 |
| `0x06000 - 0x06FFF` | UHBR Extended | ✅ DP 2.1 新增 |
| `0xF0000 - 0xF0FFF` | LTTPR | ✅ DP 2.1 新增 |

---

## DP 2.1 关键新增字段摘要

### 0x00006 MAIN_LINK_CHANNEL_CODING
| Bits | Field | DP 1.4 | DP 2.1 |
|------|-------|--------|--------|
| 0 | 8b/10b | ✅ | ✅ |
| 1 | RESERVED | — | — |
| **2** | **128b/132b** | — | **✅ 新增** |
| 7:3 | RESERVED | — | — |

### 0x00001 MAX_LINK_RATE (DP 2.1 更新)
| Value | DP 1.4 | DP 2.1 |
|-------|--------|--------|
| 06h | RBR 1.62 | ✅ |
| 0Ah | HBR 2.7 | ✅ |
| 0Ch | HBR2 5.4 | ✅ |
| 14h | HBR3 8.1 | ✅ |
| **1Eh** | — | **UHBR10 10.0 Gbps** |
| **28h** | — | **UHBR13.5 13.5 Gbps** |
| **3Ch** | — | **UHBR20 20.0 Gbps** |

### 0x0000D eDP_CONFIGURATION_CAP (eDP 1.5)
| Bits | Field | Description |
|------|-------|-------------|
| 0 | ALPM_CAP | Auxiliary Less Power Management |
| 1 | SCRAMBLER_RESET_CAP | |
| 2 | FRAMING_CHANGE_CAP | |
| 3 | PANEL_SELF_REFRESH_CAP | PSR2 |
| 4 | SINK_COUNT_ACTIVE_CAP | |
| 5 | SINK_AUDIO_DELAY_KEEP_ALIVE_CAP | |
| 6 | BACKLIGHT_ADJUSTMENT_CAP | |
| 7 | RESERVED | |

### 0x0000E ADAPTER_CAP (DP 2.1 更新)
| Bits | Field | DP 1.4 | DP 2.1 |
|------|-------|--------|--------|
| 0 | FORCE_LOAD_SENSE_CAP | ✅ | ✅ |
| 1 | ALTERNATE_I2C_PATTERN_CAP | ✅ | ✅ |
| **2** | **AUX_LDPS_CAP** | — | **✅ 新增** |
| 7:3 | RESERVED | — | — |

### 0x00115 DP_LINK_RATE_SET (DP 2.1)
| Value | Description |
|-------|-------------|
| 0h | Use MAX_LINK_RATE |
| 1h | HBR2 (5.4 Gbps) |
| 2h | HBR3 (8.1 Gbps) |
| **3h** | **UHBR10 (10.0 Gbps)** |
| **4h** | **UHBR13.5 (13.5 Gbps)** |
| **5h** | **UHBR20 (20.0 Gbps)** |

---

## 完整寄存器表

详见各 Table 2-161 至 Table 2-177。


## 1.1 DPCD Field Address Mapping Tables (Section 2.9.3)

以下基于 DP 2.1 规范 Table 2-161 至 Table 2-177 的寄存器定义。**粗体** 标记 DP 2.1/eDP 1.5 新增字段。

### Table 2-161: DPCD Receiver Capability Field (0x00000 - 0x000FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 00000h | DPCD_REV | 3:0 | Minor Revision | DPCD data structure minor revision | RO |
| | | 7:4 | Major Revision | 10h=r1.0, 11h=r1.1, 12h=r1.2, 13h=r1.3(eDP), 14h=r1.4 | RO |
| 00001h | MAX_LINK_RATE | 7:0 | MAX_LINK_RATE | 06h=RBR(1.62), 0Ah=HBR(2.7), 14h=HBR2(5.4), 1Eh=HBR3(8.1), **1Eh=UHBR10(10.0)**, **28h=UHBR13.5(13.5)**, **3Ch=UHBR20(20.0)** (128b/132b mode uses LINK_RATE_SET) | RO |
| 00002h | MAX_LANE_COUNT | 4:0 | MAX_LANE_COUNT | 01h=1, 02h=2, 04h=4 lanes | RO |
| | | 5 | POST_LT_ADJ_REQ_SUPPORTED | | RO |
| | | 6 | TPS3_SUPPORTED | Required for HBR2 | RO |
| | | 7 | ENHANCED_FRAME_CAP | Shall be 1 for r1.1+ | RO |
| 00003h | MAX_DOWNSPREAD | 0 | MAX_DOWNSPREAD | 0=No, 1=0.5% | RO |
| | | 5:1 | RESERVED | | |
| | | 6 | NO_AUX_TRANSACTION_LINK_TRAINING | | RO |
| | | 7 | TPS4_SUPPORTED | Required for HBR3 | RO |
| 00004h | NORP & DP_PWR_VOLTAGE_CAP | 0 | NORP | Ports = Value+1 | RO |
| | | 1 | CRC_3D_OPTIONS_SUPPORTED | | RO |
| | | 4:2 | RESERVED | | |
| | | 5 | 5V_DP_PWR_CAP | | RO |
| | | 6 | 12V_DP_PWR_CAP | | RO |
| | | 7 | 18V_DP_PWR_CAP | | RO |
| 00005h | DOWN_STREAM_PORT_PRESENT | 0 | DFP_PRESENT | 1=Branch with DFP(s) | RO |
| | | 2:1 | DFP_TYPE | 00=DP, 01=VGA, 10=DVI/HDMI, 11=Others | RO |
| | | 3 | FORMAT_CONVERSION | | RO |
| | | 4 | DETAILED_CAP_INFO_AVAILABLE | Shall be 1 for r1.4 | RO |
| | | 7:5 | RESERVED | | |
| 00006h | MAIN_LINK_CHANNEL_CODING | 0 | 8b/10b | 1=supported | RO |
| | | 1 | RESERVED | | |
| | | **2** | **128b/132b** | **1=supported (DP 2.1)** | **RO** |
| | | 7:3 | RESERVED | | |
| 00007h | DOWN_STREAM_PORT_COUNT | 3:0 | DFP_COUNT | | RO |
| | | 5:4 | RESERVED | | |
| | | 6 | MSA_TIMING_PAR_IGNORED | | RO |
| | | 7 | OUI_Support | | RO |
| 00008h | RECEIVE_PORT0_CAP_0 | 0 | RESERVED | | RO |
| | | 1 | LOCAL_EDID_PRESENT | | RO |
| | | 2 | ASSOCIATED_TO_PRECEDING_PORT | | RO |
| | | 3 | HBLANK_EXPANSION_CAPABLE | | RO |
| | | 4 | BUFFER_SIZE_UNIT | 0=pixel, 1=byte | RO |
| | | 5 | BUFFER_SIZE_PER_PORT | 0=per-lane, 1=per-port | RO |
| | | 7:6 | RESERVED | | |
| 00009h | RECEIVE_PORT0_CAP_1 | 7:0 | BUFFER_SIZE | Size = (Value+1) × 32 | RO |
| 0000Ah | RECEIVE_PORT1_CAP_0 | — | (same as 00008h) | | RO |
| 0000Bh | RECEIVE_PORT1_CAP_1 | — | (same as 00009h) | | RO |
| 0000Ch | I2C_SPEED | 7:0 | I2C Speed Bit Map | 01h=1K, 02h=5K, 04h=10K, 08h=100K, 10h=400K, 20h=1M | RO |
| 0000Dh | eDP_CONFIGURATION_CAP | 0 | **ALPM_CAP** | **eDP 1.5: Auxiliary Less Power Mgmt** | **RO** |
| | | 1 | **SCRAMBLER_RESET_CAP** | **eDP 1.5** | **RO** |
| | | 2 | **FRAMING_CHANGE_CAP** | **eDP 1.5** | **RO** |
| | | 3 | **PANEL_SELF_REFRESH_CAP** | **eDP 1.5: PSR2** | **RO** |
| | | 4 | **SINK_COUNT_ACTIVE_CAP** | **eDP 1.5** | **RO** |
| | | 5 | **SINK_AUDIO_DELAY_KEEP_ALIVE_CAP** | **eDP 1.5** | **RO** |
| | | 6 | **BACKLIGHT_ADJUSTMENT_CAP** | **eDP 1.5** | **RO** |
| | | 7 | RESERVED | | |
| 0000Eh | ADAPTER_CAP | 0 | FORCE_LOAD_SENSE_CAP | | RO |
| | | 1 | ALTERNATE_I2C_PATTERN_CAP | | RO |
| | | **2** | **AUX_LDPS_CAP** | **DP 2.1: AUX Low-speed Data Path Signaling** | **RO** |
| | | 7:3 | RESERVED | | |
| 0000Fh-00013h | TRAINING_AUX_RD_INTERVAL / SUPPORTED_LINK_RATES | | | 0000Fh: TRAINING_AUX_RD_INTERVAL, bit[7]=EXTENDED_RECEIVER_CAPABILITY_FIELD_PRESENT; 00010h-0001Fh: eDP SUPPORTED_LINK_RATES array | RO |
| 00021h | MSTM_CAP | 0 | MST_CAP | | RO |
| | | **1** | **SINGLE_STREAM_SIDEBAND_MSG** | **DP 2.1** | **RO** |
| 0002Eh | **ADDITIONAL_SINK_COUNT_FIELD** | **7:0** | **ADDITIONAL_SINK_COUNT** | **DP 2.1: for sink count > 7** | **RO** |
| 00030h-0003Fh | GUID | — | GUID (16 bytes) | RFC 4122 | RO |
| 00060h-0006Bh | DSC_CAPABILITY_BLOCK | — | | DSC support, algorithm rev, RC buffer, slice caps, line buffer, block pred, max bpp, color fmt | RO |

### Table 2-162: DPCD Link Configuration Field (0x00100 - 0x001FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 00100h | LINK_RATE_SET | — | (eDP only) | | W/R |
| 00101h | LANE_COUNT_SET | 4:0 | LANE_COUNT_SET | | W/R |
| | | 5 | POST_LT_ADJ_REQ_GRANTED | | W/R |
| | | 6 | ENHANCED_FRAME_EN | | W/R |
| | | 7 | UNPLUG_TO_RETRAIN | | W/R |
| 00102h | TRAINING_PATTERN_SET | 1:0 | TRAINING_PATTERN_SET | 00b=No, 01b=TPS1, 10b=TPS2, 11b=TPS3 (8b/10b) or **TPS1 (128b/132b)** | W/R |
| | | 2 | RECOVERED_CLOCK_OUT_EN | | W/R |
| | | 3 | SCRAMBLING_DISABLE | | W/R |
| | | **4** | **128b/132b_TRAINING_PATTERN** | **DP 2.1: 0=TPS1, 1=TPS2** | **W/R** |
| | | 7:5 | RESERVED | | |
| 00103h | TRAINING_LANE0_SET | 0 | VOLTAGE_SWING_SET | 0-3 | W/R |
| | | 1 | MAX_SWING_REACHED | | RO |
| | | 3:2 | PRE_EMPHASIS_SET | 0-3 | W/R |
| | | 4 | MAX_PRE_EMPHASIS_REACHED | | RO |
| 00104h | TRAINING_LANE1_SET | — | (same as 00103h) | | W/R |
| 00105h | TRAINING_LANE2_SET | — | (same as 00103h) | | W/R |
| 00106h | TRAINING_LANE3_SET | — | (same as 00103h) | | W/R |
| 00108h | MAIN_LINK_CHANNEL_CODING_SET | 0 | SET_8b/10b | | W/R |
| | | **2** | **SET_128b/132b** | **DP 2.1** | **W/R** |
| 00110h | TRAINING_LANE0_1_SET2 | 1:0 | LANE0_POST_CURSOR2_SET | | W/R |
| | | 2 | LANE0_MAX_POST_CURSOR2_REACHED | | RO |
| | | 5:4 | LANE1_POST_CURSOR2_SET | | W/R |
| | | 6 | LANE1_MAX_POST_CURSOR2_REACHED | | RO |
| 00111h | TRAINING_LANE2_3_SET2 | — | (same format as 00110h) | For Lanes 2/3 | W/R |
| 00114h | **PHY_REPEATER_MODE** | **0** | **PHY_REPEATER_MODE_SET** | **DP 2.1** | **W/R** |
| **00115h** | **DP_LINK_RATE_SET** | **2:0** | **DP_LINK_RATE_SET_MASK** | **0h=use MAX_LINK_RATE, 1h=HBR2, 2h=HBR3, 3h=UHBR10, 4h=UHBR13.5, 5h=UHBR20** | **W/R** |
| 0012Bh | DOWNSPREAD_CTRL | 0 | SPREAD_AMP | 0=off, 1=0.5% | W/R |
| | | 4 | MSA_TIMING_PAR_IGNORE_EN | | W/R |
| 001C2h | PAYLOAD_TABLE_UPDATE | 0 | PAYLOAD_TABLE_UPDATE | | W/R |

### Table 2-163: DPCD Link/Sink Device Status Field (0x00200 - 0x002FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 00200h | SINK_COUNT | 7,5:0 | SINK_COUNT | | RO |
| | | 6 | CP_READY | | RO |
| 00202h | DEVICE_SERVICE_IRQ_VECTOR | 0 | AUTOMATED_TEST_REQUEST | | W1C/RO |
| | | 2 | CP_IRQ | | W1C/RO |
| | | 3 | MCCS_IRQ | | W1C/RO |
| | | **4** | **DOWN_REP_MSG_RDY** | **1=read DOWN_REP_MSG** | W1C/RO |
| | | **5** | **UP_REQ_MSG_RDY** | **1=read UP_REQ_MSG** | W1C/RO |
| | | 6 | SINK_SPECIFIC_IRQ | | W1C/RO |
| 00204h | LANE0_1_STATUS | 0 | LANE0_CR_DONE | | RO |
| | | 1 | LANE0_CHANNEL_EQ_DONE | | RO |
| | | 2 | LANE0_SYMBOL_LOCKED | | RO |
| | | 4 | LANE1_CR_DONE | | RO |
| | | 5 | LANE1_CHANNEL_EQ_DONE | | RO |
| | | 6 | LANE1_SYMBOL_LOCKED | | RO |
| 00205h | LANE2_3_STATUS | — | (same as 00204h) | | RO |
| 00206h | LANE_ALIGN_STATUS_UPDATED | 0 | INTERLANE_ALIGN_DONE | | RO |
| | | 1 | POST_LT_ADJ_REQ_IN_PROGRESS | | RO |
| | | 6 | DOWNSTREAM_PORT_STATUS_CHANGED | | RO |
| | | 7 | LINK_STATUS_UPDATED | | RO |
| 00207h | ADJUST_REQUEST_LANE0_1 | 2:0 | VOLTAGE_SWING_LANE0 | | RO |
| | | 4:3 | PRE_EMPHASIS_LANE0 | | RO |
| | | 6:5 | VOLTAGE_SWING_LANE1 | | RO |
| | | 7 | PRE_EMPHASIS_LANE1 (bit0) | | RO |
| 0027Ah | FEC_STATUS | 0 | FEC_DECODE_EN_DETECTED | | RO |
| | | 1 | FEC_DECODE_DIS_DETECTED | | RO |
| | | 7 | FEC_ERROR_COUNT_OVERFLOW | | RO |

### Table 2-167: Power Control Field (0x00600 - 0x006FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 00600h | SET_POWER | 2:0 | SET_POWER_STATE | 001b=D0, 010b=D3, 101b=D3 AUX fully powered | W/R |
| | | 5 | SET_DN_DEVICE_DP_PWR_5V | | W/R |
| | | 6 | SET_DN_DEVICE_DP_PWR_12V | | W/R |
| | | 7 | SET_DN_DEVICE_DP_PWR_18V | | W/R |

### Table 2-168: eDP-specific Field (0x00700 - 0x007FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 00700h | eDP_SET_POWER | 0 | **DP_SET_POWER_D0** | **eDP 1.5** | **W/R** |
| | | 1 | **DP_SET_POWER_D3** | **eDP 1.5** | **W/R** |
| 00701h | **eDP_BACKLIGHT_MODE_SET** | 0 | **BACKLIGHT_ENABLE** | **eDP 1.5** | **W/R** |
| | | 1 | **BACKLIGHT_CONTROL_MODE** | **0=pwm, 1=pre-set** | **W/R** |
| 00720h | **eDP_PSR_CONFIG** | 0 | **PANEL_SELF_REFRESH_ENABLE** | **eDP 1.5 PSR2** | **W/R** |
| 00733h | **PAYLOAD_TABLE_UPDATE** | 0 | **PAYLOAD_TABLE_UPDATE** | **DP 2.1** | **W/R** |
| 00734h | **VC_PAYLOAD_ID** | 6:0 | **VC_PAYLOAD_ID_SLOT** | | **RO** |

### Table 2-169: Sideband MSG Buffers (0x01000 - 0x017FF)

| Address | Register Name | Description | Access |
|---------|--------------|-------------|--------|
| 01000h-011FFh | DOWN_REQ | Downstream Request (Source writes) | W/R |
| 01200h-013FFh | UP_REP | Upstream Reply (Source writes reply to UP_REQ) | W/R |
| 01400h-015FFh | DOWN_REP | Downstream Reply (Source reads) | RO |
| 01600h-017FFh | UP_REQ | Upstream Request (Source reads branch request) | RO |

### Table 2-170: ESI Field (0x02000 - 0x021FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 02002h | SINK_COUNT_ESI | 7,5:0 | SINK_COUNT | | RO |
| | | 6 | CP_READY | | RO |
| 02003h | DEVICE_SERVICE_IRQ_VECTOR_ESI0 | 1 | AUTOMATED_TEST_REQUEST | | W1C/RO |
| | | 2 | CP_IRQ | | W1C/RO |
| | | 3 | MCCS_IRQ | | W1C/RO |
| | | **4** | **DOWN_REP_MSG_RDY** | | W1C/RO |
| | | **5** | **UP_REQ_MSG_RDY** | | W1C/RO |
| | | 6 | SINK_SPECIFIC_IRQ | | W1C/RO |
| 02004h | DEVICE_SERVICE_IRQ_VECTOR_ESI1 | 0 | RX_GTC_PRIMARY_REQ_STATUS_CHANGE | | W1C/RO |
| | | 1 | LOCK_ACQUISITION_REQUEST | | W1C/RO |
| | | 2 | CEC_IRQ | | W1C/RO |
| 02005h | LINK_SERVICE_IRQ_VECTOR_ESI0 | 0 | RX_CAP_CHANGED | | W1C/RO |
| | | 1 | LINK_STATUS_CHANGED | | W1C/RO |
| | | 2 | STREAM_STATUS_CHANGED | | W1C/RO |
| | | 3 | HDMI_LINK_STATUS_CHANGED | | W1C/RO |
| | | 4 | CONNECTED_OFF_ENTRY_REQUESTED | | W1C/RO |
| 0200Ch-0200Fh | LANE_STATUS_ESI | — | Same as 00204h-00207h | | RO |

### Table 2-171: Extended Receiver Capability (0x02200 - 0x022FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 02200h | DPCD_REV | — | (same as 00000h) | | RO |
| 02215h | **MAIN_LINK_CHANNEL_CODING** | **2** | **128b/132b** | **DP 2.1** | **RO** |
| 02216h | **DP13_FEATURE_ENUMERATION_LIST** | 0 | **CABLE_UPDATE_CAP** | | **RO** |
| 02219h | **CHANNEL_CODING_SET_CAP** | — | **128b/132b eq done** | **DP 2.1** | **RO** |

### Table 2-172: Protocol Converter Extension (0x03000 - 0x030FF)

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 03000h | PROTOCOL_CONVERTER_CAP | 0 | TYPEC_HDMI Cable | | RO |
| | | 1 | TYPEC_DP_CABLE | | RO |
| 03004h | PROTOCOL_CONVERTER_CTRL | 0 | HDMI_ENABLE | | W/R |
| 03005h | PROTOCOL_CONVERTER_CTRL_2 | 0 | HDMI_LINK_SELECT | | W/R |
| 0300Ah | CEC_TUNNELING_CAP | 0 | CEC_TUNNELING_CAPABLE | | RO |
| 0300Bh | CEC_TUNNELING_CTRL | 0 | CEC_TUNNELING_ENABLE | | W/R |
| 0300Ch-0300Dh | CEC_LOGICAL_ADDRESS_MASK | — | | | W/R |
| 03010h | CEC_RX_DATA | — | | | RO |
| 03020h | CEC_TX_DATA | — | | | W/R |

### Table 2-173: DSC Encoder (0x03100 - 0x031FF)

| Address | Register Name | Bits | Description | Access |
|---------|--------------|------|-------------|--------|
| 03100h | DSC_DECODER0_OPERATION_MODE | 0 | DSC_ENABLE | W/R |
| 03101h | DSC_DECODER0_COMPRESSION | 0 | DSC_SLICE_COUNT_MISMATCH | RO |
| 03180h | DSC_LINE_BUFFER_BIT_DEPTH | 3:0 | Same as 00065h | RO |
| 03184h | DSC_PICTURE_PARAMETER_SET | — | PPS fields | W/R |

### Table 2-174: FEC Extended (0x04000 - 0x04FFF) — DP 2.1 新增

| Address | Register Name | Bits | Bit Field Name | Description | Access |
|---------|--------------|------|----------------|-------------|--------|
| 04000h | **FEC_CAPABILITY_1** | **0** | **FEC_CAPABLE** | **1=FEC supported** | **RO** |
| | | **1** | **UNCORRECTED_BLOCK_ERROR_COUNT_CAPABLE** | | **RO** |
| | | **2** | **CORRECTED_BLOCK_ERROR_COUNT_CAPABLE** | | **RO** |
| | | **3** | **BIT_ERROR_COUNT_CAPABLE** | | **RO** |
| | | **4** | **PARITY_BLOCK_ERROR_COUNT_CAPABLE** | | **RO** |
| 04001h | **FEC_CAPABILITY_2** | 0 | **ARBITRATION_NOT_REQUIRED** | | **RO** |
| 04010h | **FEC_CONFIGURATION** | **0** | **FEC_ENABLE** | | **W/R** |
| 04011h | **FEC_SELECTIVE_REPEAT_ENABLE** | 0 | **SELECTIVE_REPEAT_ENABLE** | | **W/R** |
| 04020h | **FEC_ERROR_COUNTER_0** | — | **UNCORRECTED_BLOCK_ERROR_COUNT** | | **RO** |
| 04022h | **FEC_ERROR_COUNTER_1** | — | **CORRECTED_BLOCK_ERROR_COUNT** | | **RO** |
| 04024h | **FEC_ERROR_COUNTER_2** | — | **BIT_ERROR_COUNT** | | **RO** |
| 04026h | **FEC_ERROR_COUNTER_3** | — | **PARITY_BIT_ERROR_COUNT** | | **RO** |

### Table 2-175: UHBR Extended (0x06000 - 0x06FFF) — DP 2.1 新增

| Address | Register Name | Bits | Description | Access |
|---------|--------------|------|-------------|--------|
| 06000h | **UHBR_CAPABILITY** | — | **UHBR link rate and coding capabilities** | **RO** |
| 06001h | **UHBR_LINK_RATE_CAP** | — | **UHBR10/13.5/20 rate support bits** | **RO** |
| 06010h | **UHBR_CONFIGURATION** | — | **128b/132b training parameters** | **W/R** |
| 06011h | **UHBR_LINK_RATE_SET** | — | **Active UHBR link rate** | **W/R** |

### Table 2-176: LTTPR Repeater (0xF0000 - 0xF0FFF) — DP 2.1

| Address | Register Name | Bits | Description | Access |
|---------|--------------|------|-------------|--------|
| F0000h | DPCD_REV | — | LTTPR DPCD revision | RO |
| F0001h | MAX_LINK_RATE | — | Max link rate supported by repeater | RO |
| F0002h | MAX_LANE_COUNT | 4:0 | Max lane count | RO |
| F0004h | AUX_RD_INTERVAL | — | LTTPR training AUX read interval | RO |
| F0008h | LTTPR_COUNT | 4:0 | Number of LT-tunable PHY Repeaters | RO |
| F0010h | PHY_REPEATER_MODE | 0 | Repeater mode setting | W/R |
| F0030h | TRAINING_PATTERN_SET | — | Same format as 00102h | W/R |
| F0031h-0034h | TRAINING_LANE_SET | — | Per-lane training settings | W/R |
| F0040h | LANE0_1_STATUS | — | Same format as 00204h | RO |
| F0042h | LANE_ALIGN_STATUS_UPDATED | — | Same format as 00206h | RO |
| F0290h | LTTPR_MAX_EQ_READS | — | Max EQ reads during training | RO |
| F0294h | LTTPR_PHY_TEST_MODE | — | PHY test mode control | W/R |
