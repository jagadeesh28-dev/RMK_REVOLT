# Section 8: HERMES Hardware Platform & Independent Analog Safety Interlock

## 8.1 SELV Testbed Architecture

The **HERMES** platform (`Hardware for Evaluation, Risk Mitigation, and Estimation in Second-life`) operates under Safety Extra-Low Voltage (SELV, $<60\text{V}$ DC, 4S1P 12.8V nominal, 20Ah format). The physical architecture couples an embedded control core with an independent analog protection chain.

```
+-----------------------------------------------------------------------------------+
|                        HERMES HARDWARE SAFETY ARCHITECTURE                        |
|                                                                                   |
|  [Battery Under Test] <===============================> [Programmable DC Load]    |
|       (4S LFP)                         |                   (0-10A Active Sink)    |
|                                        |                                          |
|                                 [JD1912 Contactor] (40A Rated)                    |
|                                        ^                                          |
|                                        | (Coil Enable: Hardware AND Gate)         |
|                     +------------------+------------------+                       |
|                     |                                     |                       |
|           [LM393 Window Comparator]             [TPS3823 Watchdog Supervisor]     |
|             (Analog UVP/OVP Veto)                 (Hardware Firmware Hang Trip)   |
|           Trip Latency: 11.8 ms                 Trip Latency: 194.2 ms            |
|                     ^                                     ^                       |
|                     |                                     |                       |
|             (Analog Divider)                      (Hardware WDI Strobe)           |
|                     |                                     |                       |
|             [Battery Terminals]                   [ESP32-S3 Microcontroller]      |
+-----------------------------------------------------------------------------------+
```

## 8.2 The Failure of Software-Only Safety Authority

A pervasive deficiency in automated battery cyclers is relying on software tasks or RTOS daemons for over-voltage and over-temperature shutdown. If an operating system hangs, if an ADC driver deadlocks, or if a stack overflow corrupts the main control thread with GPIO pins held in an active `HIGH` state, current continues flowing into an overloaded cell.

In SECONDShift, **software is strictly advisory**. The power contactor coil drive circuit requires continuous, concurrent hardware authorization from three independent analog mechanisms:
1. **LM393 Dual Analog Window Comparator:** Implements hardware-referenced analog window detection ($V_{\text{low}} = 2.00\text{ V/cell}$, $V_{\text{high}} = 3.65\text{ V/cell}$). If the terminal voltage leaves this analog threshold window, the comparator open-collector output immediately pulls down the gate of the low-side N-channel MOSFET, de-energizing the contactor coil.
2. **TPS3823 Hardware Supervisory Watchdog:** Requires a periodic hardware strobe on the `WDI` pin every $<200\text{ ms}$. If firmware crashes, stalls in a loop, or freezes with GPIO pins held `HIGH`, the TPS3823 pulls `RESET` low and disconnects the contactor.
3. **KSD9700 Bimetallic Thermal Snap Switch:** Surface-mounted on the battery busbar, opening mechanically at $60.0^\circ\text{C} \pm 3^\circ\text{C}$ without requiring electrical power.

## 8.3 Observed Hardware Latency Benchmarks

Hardware protection latencies were empirically recorded on a Rigol DS1054Z 50 MHz digital storage oscilloscope during bench fault-injection testing:

| Protection Mechanism | Monitored Fault Condition | Target Design Specification | Observed Hardware Bench Latency [PHYSICAL] |
| :--- | :--- | :---: | :---: |
| **LM393 Analog Comparator** | Under-Voltage Excursion ($V < 2.00\text{V}$) | $< 15.0\text{ ms}$ | **$11.8\text{ ms}$** |
| **LM393 Analog Comparator** | Over-Voltage Excursion ($V > 3.65\text{V}$) | $< 15.0\text{ ms}$ | **$12.2\text{ ms}$** |
| **TPS3823 Hardware Watchdog** | Firmware Freeze / WDI Timeout | $< 250.0\text{ ms}$ | **$194.2\text{ ms}$** |
| **Fast-Acting Thermal Fuse** | Direct Short Circuit Overcurrent | $< 25.0\text{ ms}$ | **$18.5\text{ ms}$** |

These single-instance bench captures confirm that the physical hardware disconnect operates within milliseconds, completely insulating the physical cell from software estimator failures.
