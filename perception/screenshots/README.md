# PipeGen evidence (captured 2026-10-15, PipeGen v0.5.1, RTX 2000 Ada)

| File | Stage | Shows |
|---|---|---|
| 01a_requirement_outputs_mqtt_metadata_display.png | 1 Requirement | Video-file input; outputs: MQTT localhost:1883, JSON metadata file, live display |
| 01b_requirement_flow_draft.png | 1 Requirement | First flow draft |
| 01c_requirement_scene_lighting_clahe.png | 1 Requirement | Scene question; PipeGen added CLAHE for day/night lighting |
| 01d_requirement_task_details_custom_model.png | 1 Requirement | Task details: custom YOLOv8n ONNX model path |
| 01e_requirement_code_sources_local_model.png | 1 Requirement | Code sources: local custom model |
| 01f_requirement_final_flow.png | 1 Requirement | Final flow |
| 02a_pipeline_ir_perception_subgraph.png | 2 Pipeline IR | Video source → preprocess → WildGuard YOLOv8n → detection decoding → sink |
| 02b_pipeline_ir_requirement_checks_passed.png | 2 Pipeline IR | All requirement checks passed |
| **02_pipeline_ir.png** | 2 Pipeline IR | **Pipeline IR node graph (required evidence)** |
| 02c_pipeline_ir_approved_onnx_check.png | 2→3 | PIR approved, ONNX model check |
| 03_onnx_check_layer_inspection.png | 3 Model | 234 layers, 232 supported on TensorRT, 0 unresolved |
| 03b_onnx_graph_visualization.png | 3 Model | ONNX graph, per-node TensorRT support |
| 05a_pipeline_compiling.png | 5 Run | Pipeline compilation with the TensorRT engine |
| 05b_pipeline_compiled_run_options.png | 5 Run | Pipeline compiled; Run / latency tracing / VMS options |
| 05c_pipeline_summary.png | 5 Run | PipeGen's summary of the generated DeepStream pipeline |
| **05_live_run_tapir_30fps.png** | 5 Run | **Live run: tapir boxed, 30 FPS, 0 dropped frames (required evidence)** |
| 05d_live_run_jaguarundi.png | 5 Run | Jaguarundi boxed |
| 05e_live_run_puma.png | 5 Run | Puma boxed |
| 05f_live_run_negative_cat_false_positive.png | 5 Run | Known limitation: domestic cat labelled "maned wolf" by the closed-set model |
| 06a_vms_console_tapir_detections.png | 5 Run | VMS console: tapir detection events table |
| 06b_vms_console_giant_anteater_detections.png | 5 Run | VMS console: giant anteater detection events table |

PipeGen export (the deliverable folder): `../pipegen_export/` (run with `./run.sh --input <video>`),
archive `../pipegen-yolo-wildlife-tracking-and-mqtt.tar.gz`. Real PipeGen JSON output for the demo reel:
`../reports/pipegen_metadata_demo_reel.json`, scored per clip in `docs/evidence/video_test/pipegen/report.md`.

Compiler-stage reports are in `../reports/`:

| File | Shows |
|---|---|
| **04_fp16_tensorrt_engine_compiled.png** | **TensorRT FP16 engine: 8.4 s build, 10.9 MB, 174 TRT layers (required evidence)** |
| **04_fp16_speed_report.png** | **Per-layer FP16 latency on the GPU (benchmark report)** |
| 04b_fp16_accuracy_vs_fp32_onnx.png | FP16 engine vs FP32 ONNX: 1.000 on all metrics (30 samples) - compiling lost no accuracy |
| 04c_benchmark_options.png / 04d_accuracy_dataset_choice.png | Benchmark and accuracy options |
| 04e_accuracy_vs_coco_NOT_APPLICABLE.png | Scored against COCO 2017 labels → 0.000. **Not meaningful**: our 5 Brazilian species are not COCO classes. Kept for transparency only. |
