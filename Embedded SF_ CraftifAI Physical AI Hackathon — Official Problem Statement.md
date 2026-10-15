# Embedded SF: CraftifAI Physical AI Hackathon — Official Problem Statement

**Theme:** Building Physical AI Systems That See, Decide and Act — with CraftifAI PipeGen and FirmGen

The next generation of AI doesn't live only in a chat window — it lives in cameras, sensors, boards and actuators. Physical AI systems perceive the real world through vision models running at the edge, decide what matters, and act through firmware on microcontrollers that drive lights, motors, alarms and radios.

Embedded SF challenges you to build a Physical AI system on real hardware. Choose your track: use CraftifAI PipeGen to turn a sentence into a GPU-accelerated vision pipeline that sees the world, or CraftifAI FirmGen to turn a PRD into working, traceable firmware that acts in it. Teams that combine both into one closed loop are eligible for a bonus prize.

---

## Core Challenge

Pick one of the two tracks below and build an innovative Physical AI application with it:

* **Track A — PipeGen (Perception):** Build an edge vision pipeline — detection, pose, tracking or analytics — compiled to TensorRT and running on DeepStream on an NVIDIA GPU or Jetson, producing results a person or system can act on.  
* **Track B — FirmGen (Action):** Build requirements-driven firmware for an ESP32 or STM32 board that senses and acts in the physical world — driving sensors, actuators, LEDs, displays, motors or BLE/Wi-Fi radios.  
* **Closed Loop (optional bonus):** Use both tools together, so the vision pipeline's output (MQTT, JSON, serial or BLE) drives the firmware's physical action in real time.  
* **Live Intelligence (optional bonus, Track B):** Add runtime telemetry and debugging to your firmware and show the board's internal state live during the demo.  
* **Edge Optimization (optional bonus, Track A):** Quantize your models to INT8 or deploy the pipeline on a Jetson for a truly embedded, low-power system.

---

## Mandatory Requirements

### Track A — PipeGen: Labs link : [PipeGen v0.5.1 Lab](https://docs.google.com/document/d/15HpN0QEd8UMjtQVhQ_OdcJoq09JsuSZIBh-VntsnfB4/edit?usp=sharing) / PRD : [ESP32\_BLE\_FirmGen\_Simple\_PRD.pdf](https://drive.google.com/file/d/1T6PVA_S-QZf1Z_Zkv1YoGlz_7HVeuOF-/view?usp=sharing)

* **Full PipeGen Flow:** Build your pipeline through all five stages — Requirement, Pipeline IR, Model, Compiler and Run. Not just a notebook script.  
* **TensorRT Engine:** At least one model must be compiled to a TensorRT engine, with its speed report from PipeGen.  
* **Live Run:** The pipeline must run live on a video file, USB camera, CSI camera or RTSP stream on an NVIDIA GPU machine or Jetson.  
* **Actionable Output:** The pipeline must produce something beyond boxes on a screen — a JSON or MQTT feed, RTSP stream, alerts or analytics that a person or system can act on.

### Track B — FirmGen: Labs link : [FirmGen Hands On Lab.pdf](https://drive.google.com/file/d/1O1T4MvvToPP5rbnfR8O4Ymf4qg4haU5g/view?usp=sharing)

* **PRD-Driven Build:** Build your firmware from a PRD (uploaded or written with Help me write one), with a reviewed and frozen requirement set. Skip the specification bring-up alone does not qualify.  
* **Real Hardware:** Flash the firmware to a physical ESP32 or STM32 board. Simulation-only projects are not eligible.  
* **Acceptance Evidence:** Show your PRD acceptance criteria met on the board — UART or Monitor output plus the physical behavior.  
* **Traceability:** Submit the FirmGen traceability report, linking each requirement to its code and tests.

### Bonus Prizes (any track):

* **Closed Loop:** Use PipeGen and FirmGen together, where a perception event (person detected, line crossed, pose recognized) triggers a physical action on the board in real time.  
* **Live Intelligence (Track B):** Enable telemetry and show live runtime data or breakpoints from the board during the demo.  
* **Edge Optimization (Track A):** Run an INT8 engine or deploy on a Jetson, and report the speed, power and accuracy trade-off from PipeGen's reports.

**Deep Integration:** Your chosen tool must be load-bearing in the product, not bolted on. A project that uses PipeGen or FirmGen as an afterthought is grounds for disqualification.

---

## Technology Primers

### PipeGen — From a Sentence to a Running Edge AI Pipeline

PipeGen is CraftifAI's tool for building edge AI vision pipelines. Describe what you want in plain words and PipeGen guides you through five stages: Requirement, Pipeline IR, Model, Compiler and Run. It picks code and models from CraftifAI's catalog (or GitHub via Deep Search), compiles each ONNX model into a TensorRT engine in FP32, FP16 or INT8, measures speed, power and accuracy, and generates a DeepStream app with a run.sh. Outputs include live display, saved video, RTSP, JSON metadata files and MQTT. Runs on an x86-64 Linux PC with an NVIDIA GPU, or an NVIDIA Jetson with JetPack 6\.

### FirmGen — From PRD to Working Firmware

FirmGen is CraftifAI's requirements-driven firmware development workflow. Upload a PRD and FirmGen generates categorized requirements (tagged Explicit or Inferred), task lists and acceptance criteria, then implements, builds, flashes and monitors the firmware on your board. It produces requirement-linked unit tests, a design document and a traceability report, with Git built in. Supports ESP32 (ESP-IDF v5.5) and STM32, with three execution paths: Direct Prompt, Auto Mode and Category-wise Manual Review.

### Live Intelligence (Optional) — Runtime Visibility for Firmware

FirmGen's Live Intelligence panel adds breakpoints and an RTOS / System Monitor. Enable Telemetry injects telemetry into your firmware, rebuilds, flashes and streams live data — ideal for showing judges what your board is doing internally as the vision pipeline drives it.

---

## Suggested Problem Tracks

| Track | Tool | Problem | Solution Summary |
| :---- | :---- | :---- | :---- |
| 1\. Workplace Safety Sentinel | PipeGen | Workers enter hazard zones or skip PPE, and nobody notices until an incident. | Person detection plus zone or PPE checks on a site camera, with alerts published over MQTT and a JSON incident log. |
| 2\. Fall Detection and Elder Care | PipeGen | Falls at home go unnoticed for hours. | Pose estimation flags a fall posture held over time and sends an alert, with privacy blur before any frame is saved. |
| 3\. Retail Shelf and Queue Monitor | PipeGen | Stores lose sales to empty shelves and long checkout lines. | Object counting and queue-length analytics from an aisle camera, streamed to a dashboard. |
| 4\. Traffic and Crosswalk Analytics | PipeGen | Cities lack live counts of pedestrians, cyclists and cars at crossings. | Detection and line-crossing counts per class, with INT8 on a Jetson for a pole-mounted unit. |
| 5\. Industrial Visual Inspection | PipeGen | Defects slip past manual inspection on a conveyor. | Defect or anomaly detection per frame, using Deep Search to find a domain-specific model. |
| 6\. Smart Environmental Monitor | FirmGen | Indoor air, temperature and noise problems go unmeasured. | ESP32 reads kit sensors, flags thresholds on LEDs or a display, and broadcasts readings over BLE or Wi-Fi. |
| 7\. Wearable Health and Activity Tracker | FirmGen | Activity and posture data needs a low-power, always-on device. | ESP32 with an IMU counts steps, detects falls or bad posture, and advertises over BLE, with traceable timing requirements. |
| 8\. Predictive Maintenance Node | FirmGen | Motors and pumps fail without warning. | STM32 samples vibration and temperature, detects anomalies on-device, and reports status over UART or Ethernet. |
| 9\. Smart Access and Asset Tracker | FirmGen | Teams lose track of tools and who entered a room. | ESP32 BLE beacons and a reader node log presence, with Live Intelligence showing state during the demo. |
| 10\. Robot Perception-to-Actuation Loop | Both (bonus) | Small robots need vision and motor control to work together reliably. | PipeGen detects targets or obstacles and streams positions; FirmGen motor-control firmware follows or avoids them. |
| 11\. Gesture-Controlled Devices | Both (bonus) | Touchless control for kitchens, labs and accessibility users. | PipeGen recognizes gestures from pose keypoints; FirmGen maps each gesture to a relay, servo or light action. |
| 12\. Open Innovation Track | Either | Any problem where seeing or acting in the physical world matters. | Build on PipeGen or FirmGen — or both for the Closed Loop bonus — and bring your own idea. |

---

## Submission & Deliverables

### What to Submit:

* **Working Prototype:** Live demo on hardware at the venue — your PipeGen pipeline running live or your FirmGen firmware working on the board.  
* **Source Code:** Repository link, including the PipeGen export folder or the FirmGen project pushed through FirmGen's Git view.  
* **Project Description:** The problem and your chosen track. Track A: the PipeGen pipeline (inputs, tasks, models, precision, outputs). Track B: the FirmGen PRD and frozen requirements. If you used both, explain how they connect. Mention any bonus you are going for: Closed Loop, Live Intelligence or Edge Optimization.  
* **Evidence:** Track A: screenshots of the Pipeline IR node graph and the TensorRT speed report. Track B: the FirmGen traceability report and the board's UART or Monitor output.  
* **Pitch Deck/Video:** Optional.

### How to Submit:

* **Setup:** Install the tool for your track (PipeGen or FirmGen) and sign in with your CraftifAI account before you start building.  
* **Sign up:** https\://developer.craftifai.com/dashboard?tab=downloads  
* **Final Submission:** FirmGen : [https\://forms.gle/bnocK9CNLndiZLwf8](https://forms.gle/bnocK9CNLndiZLwf8) / PipeGen : https\://forms.gle/eJyeCKCG2UH757QZ8  
* **Questions?** Ask in `#community-support` on Discord, or find a CraftifAI mentor at the hardware desk.  
* **Workshops:** Both PipeGen and FirmGen labs run parallely from 10am \- 12pm.  
* **Submission Deadline:** 4:00 pm

---

## Setup Checklist

* **PipeGen:** (Track A) Install PipeGen v0.5.1 and confirm `pipegen --version` prints `0.5.1`. Run on an x86-64 Linux PC with an NVIDIA GPU or a Jetson on JetPack 6, in an X11 desktop session. Keep your videos under `/home`.  
* **FirmGen:** (Track B) Install FirmGen v0.4.1 and its prerequisites from the CraftifAI developer portal. Confirm FirmGen is using ESP-IDF v5.5 for ESP32 projects.  
* **Hardware:** Collect your kit — a USB camera for Track A; an ESP32 or STM32 board, USB cable, sensors and actuators, for Track B. Use an ESP32 if your project needs BLE or Wi-Fi; the STM32 boards in the kit do not have BLE.  
* **Bridge:** Closed Loop bonus only: decide early how perception reaches the board (MQTT, JSON, serial or BLE) and write it into your FirmGen PRD as a requirement.  
* **Live Intelligence (optional):** Enable telemetry in FirmGen if you want to show live board state during judging.

---

## Judging

Tracks A and B are judged separately. Judging will weigh how meaningfully your chosen tool is woven into the core product, and whether it works live on hardware. Integrations that feel bolted on rather than load-bearing will be scored down. A command that completes is not the same as a system that works — show the evidence.