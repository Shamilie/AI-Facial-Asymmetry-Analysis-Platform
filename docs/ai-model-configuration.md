# AI Model Configuration & Provider Adapter Guide

## 1. Task-Specific Provider Compatibility Matrix

The platform never assumes that a single AI provider supports every clinical vision or language task. Each pipeline task is bound to an explicit `TaskType` and validated by `backend/app/ai/providers/registry.py` before activation:

| Task Type | Supported Provider Families | Default Seeded Adapter | Primary Clinical Role |
|---|---|---|---|
| `ImageQuality` | `OpenAI`, `LocalModel`, `CustomGPU`, `Demo` | `Demo` / Heuristic CV | Blur, lighting, orientation, framing, and occlusion screening |
| `FacialLandmarks` | `MediaPipe`, `LocalModel` (HRNet/RTMPose), `CustomGPU`, `NVIDIA`, `Demo` | `MediaPipe` / `Demo` | 16 standardized facial anthropometry landmarks |
| `FacialSegmentation` | `LocalModel` (U-Net/SegFormer), `CustomGPU`, `NVIDIA`, `Demo` | `Demo` | Facial midline vector and bilateral soft-tissue contour masks |
| `Reconstruction3D` | `LocalModel` (DECA-compatible), `CustomGPU`, `NVIDIA`, `Demo` | `Demo` | 3D surface mesh (`.obj`/`.ply`), 3D landmarks, Dijkstra geodesic paths |
| `OPGLandmarks` | `LocalModel` (PyTorch/ONNX), `CustomGPU`, `NVIDIA`, `Demo` | `Demo` | 7 panoramic mandibular radiographic landmarks (`Co`, `Cor`, `Go_OPG`, `Xi`, `MF`, `Ag`, `Me_OPG`) |
| `OPGSegmentation` | `LocalModel` (U-Net), `CustomGPU`, `NVIDIA`, `Demo` | `Demo` | Mandibular cortical contour, rami, condyles, and fixation ROI |
| `ReportGeneration` | `OpenAI`, `NVIDIA`, `CustomGPU`, `LocalModel`, `Demo` | `Demo` | Structured 13-section clinical research summary |

## 2. Privacy & Security Controls for External AI Providers

1. **External Upload Gate (`ALLOW_EXTERNAL_AI_UPLOADS`)**:
   - By default, `ALLOW_EXTERNAL_AI_UPLOADS=false` in `.env`.
   - Any attempt to invoke an external cloud API (`OpenAI`, `NVIDIA`, or remote `CustomGPU`) with identifiable clinical images is blocked unless both `ALLOW_EXTERNAL_AI_UPLOADS=true` and the provider's `allow_external_upload=true` flag are enabled.
2. **Backend-Only API Key Resolution**:
   - Database records store only the **environment variable name** (e.g., `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `CUSTOM_GPU_TOKEN`) in `api_key_env_var`.
   - Secret values are never stored in the database or returned to the frontend.
3. **Synthetic Demo Fallback Labeling**:
   - Whenever the `Demo` adapter is used (or triggered as a fallback), `is_demo=true` is recorded on the `AIAnalysisJob` and displayed as a `SYNTHETIC DEMO ADAPTER` badge in the UI and exported reports.
