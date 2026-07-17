# Customer Response — YOLO Detection Naming Update

**Subject:** Re: Requested Naming Updates for the YOLO Detection ROS 2 Integration Specification

Dear Mr. Chin,

Thank you for your detailed naming proposal.

We agree that the interface should use generic terminology so that it can support different detection targets in the future. We will update the prototype specification as follows:

| Current | Updated |
| --- | --- |
| Grass Detection ROS 2 Integration Specification | YOLO Detection ROS 2 Integration Specification |
| Grass Detection | YOLO Detection |
| GrassSegment | DetectedInstance |
| GrassSegmentationArray | DetectedInstanceArray |
| `/grass_segments` | `/detected_instances` |

We will also use `instances[]` as the array field name and replace plant-specific wording with generic terms such as “detection target” and “detected target instance.”

We selected `DetectedInstance` rather than `SegmentedInstance` because the interface supports both detection-only models and segmentation models. The `polygon` field remains optional.

The data fields `class_name`, `score`, `bbox`, and `polygon` remain unchanged. The document version is updated to 1.1.0 to record these prototype naming changes.

The corresponding message definitions and ROS 2 endpoints will be updated consistently for the prototype implementation.

Best regards,

Quy
ViZO
