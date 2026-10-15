# Hardware

## Bill of materials

| Item | Priority | Notes |
|---|---|---|
| NVIDIA GPU laptop/desktop (x86-64 Linux) or Jetson (JetPack 6) | P0 | Runs PipeGen. Build TensorRT engines on this machine. |
| USB camera + tripod | P0 | Fixed position, consistent lighting |
| ESP32 DevKit (+ 1 spare, flashed with the same firmware) | P0 | Wi-Fi required |
| HC-SR04 ultrasonic sensor | P0 | 5 V part: needs the ECHO divider |
| HC-SR501 PIR | P0 | |
| Red, amber and green LEDs + 220 Ohm resistors | P0 | |
| High-intensity LED / strip + logic-level N-MOSFET (e.g. AO3400, IRLZ44N) + 100 Ohm gate resistor + 10 kOhm pull-down | P0 | "Warning sign" |
| Buzzer (active, or passive for tones) | P0 | |
| 1 kOhm + 2 kOhm resistors | P0 | ECHO 5 V to 3.3 V divider |
| Travel router or phone hotspot | P0 | Venue Wi-Fi often isolates clients |
| Breadboard, jumpers, data-capable USB cables, power strip | P0 | |
| Printed species cards, tablet with test images, backup MP4s under /home | P0 | |
| Cardboard road mock-up with a roadside "sign" | P1 | Makes the demo readable for judges |
| Stepper + A4988/DRV8825 + 9-12 V supply | P2 | Stretch: barrier (WG-ACT-05) |

## Pin map (must match PRD section 3)

| Function | ESP32 GPIO | Wire to |
|---|---|---|
| HC-SR04 TRIG | 25 | TRIG |
| HC-SR04 ECHO | **34 via divider** | ECHO → 1 kOhm → GPIO34, GPIO34 → 2 kOhm → GND |
| PIR OUT | 27 | OUT (PIR VCC at 5 V) |
| LED green | 16 | 220 Ohm → LED → GND |
| LED amber | 17 | 220 Ohm → LED → GND |
| Red strobe (MOSFET gate) | 26 | 100 Ohm → gate, 10 kOhm gate → GND |
| Buzzer | 33 | Buzzer + (through a transistor if it draws more than 12 mA) |
| Onboard LED | 2 | built in |

```
 HC-SR04 ECHO ──[1k]──┬── GPIO34          5V LED supply ──► LED strip + ──► LED strip − ──► MOSFET drain
                      [2k]                                                     MOSFET source ──► GND (common)
                      │                     GPIO26 ──[100R]──► MOSFET gate ──[10k]──► GND
                     GND
```

## Electrical safety checklist

- [ ] ECHO measured at 3.3 V or less on GPIO34 with a multimeter
- [ ] High-power LEDs / motors on their own supply, **common GND** with the ESP32
- [ ] MOSFET gate resistor and pull-down fitted, so outputs stay OFF while the ESP32 boots
- [ ] Nothing pulls GPIO 0, 2, 12 or 15 high at boot
- [ ] Final wiring photographed into this folder (`wiring_top.jpg`, `wiring_side.jpg`)

## Network

- Laptop, broker and ESP32 on the same router or hotspot. Note the laptop IP and set the broker URI in `menuconfig`.
- `./scripts/check_env.sh` prints the laptop IP and checks that the node's retained status is `online`.
