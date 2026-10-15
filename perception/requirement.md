# PipeGen Stage 1 - Requirement (paste into PipeGen)

> Detect tapir, jaguarundi, maned wolf, puma and giant anteater in a live USB camera stream using my custom
> YOLOv8n model (5 classes, 640x640 ONNX, labels in labels.txt). Track each animal with a multi-object tracker,
> flag when it is inside the road zone in the lower part of the frame, publish a JSON message over MQTT
> (broker localhost:1883, topic wildguard/pipegen/raw) for every tracked animal in each frame, save JSON
> metadata, and output an annotated video on screen and as an RTSP stream.

Fallback sentence if custom-model import needs the catalog route first:

> Build a YOLOv8 object detection pipeline on a USB camera with tracking, MQTT output to localhost:1883
> topic wildguard/pipegen/raw, JSON metadata and an RTSP output. I will replace the model with my
> custom 5-class YOLOv8n ONNX in the Model stage.
