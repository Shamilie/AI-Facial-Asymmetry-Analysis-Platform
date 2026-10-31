# Validated Measurement & Biostatistical Methodology

## 1. Core Geometric Formulas (`backend/app/measurements/engine.py`)

### 1.1 2D Euclidean Pixel Distance
$$d_{\text{px}} = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}$$

### 1.2 Physical Calibration Conversion (`FrontalPhoto`, `RightLateralPhoto`, `LeftLateralPhoto`)
$$\text{mm\_per\_pixel} = \frac{\text{known\_marker\_length\_mm}}{\text{measured\_marker\_length\_px}}$$
$$d_{\text{mm}} = d_{\text{px}} \times \text{mm\_per\_pixel}$$

> **Strict Calibration Rule**: Generic display/CSS assumptions (`1 mm = 3.78 px` at 96 DPI) are prohibited. If a calibration record has `is_physical = false` or is missing for the required image view, the measurement engine outputs raw pixel distances with `unit = "px (Unscaled)"`, `is_unscaled = true`, and `status = "Unscaled"`.

### 1.3 OPG Panoramic Magnification & Regional Adjustment
Orthopantomograms exhibit non-uniform horizontal and vertical magnification depending on focal trough position. The engine applies machine magnification and regional correction factors (`ramus_factor`, `body_factor`, `condyle_factor`):
$$d_{\text{OPG, mm}} = \frac{d_{\text{px}} \times \text{mm\_per\_pixel}}{\text{magnification\_factor}} \times f_{\text{region}}$$

### 1.4 Bilateral Asymmetry Index (%)
For any paired bilateral measurement with Right value $R$ and Left value $L$:
$$\text{Absolute Difference} = |R - L|$$
$$\text{Asymmetry Index (\%)} = \frac{|R - L|}{R + L} \times 100$$

- **Zero-Denominator Guard**: If $R + L \le 0$ or either side is negative, `asymmetry_index = null` and `status = "Invalid"`.
- **Missing / Occluded Landmark Guard**: If any required landmark is missing or marked `NotIdentifiable`, the measurement is never fabricated (`status = "MissingData"`).

### 1.5 Angular Measurements (Gonial Angle & Commissural Cant)
For three-point angles $\angle ABC$ with vertex at $B$ (e.g., `Co – Go – Me` on OPG or `Tr – Go – Me` on lateral photographs):
$$\theta = \arccos\left(\frac{\vec{BA} \cdot \vec{BC}}{\|\vec{BA}\| \|\vec{BC}\|}\right) \times \frac{180^\circ}{\pi}$$

### 1.6 3D Surface Geodesic Distance
On the reconstructed 3D triangular mesh (`backend/app/ai/reconstruction/mesh.py`), surface distances (e.g., `Tragus -> Subnasale` and `Tragus -> Pogonion`) are computed via Dijkstra's shortest-path algorithm along mesh edges weighted by 3D Euclidean edge length. All 3D geodesic measurements carry an explicit warning that computational surface paths approximate clinical flexible-tape measurements and require paired physical validation.

## 2. Biostatistical Reliability Formulas (`backend/app/measurements/statistics.py`)

1. **Intraclass Correlation Coefficient `ICC(2,1)`** (Two-way random effects, absolute agreement, single rater/method):
   $$\text{ICC}(2,1) = \frac{MS_R - MS_E}{MS_R + (k - 1)MS_E + \frac{k}{n}(MS_C - MS_E)}$$
   Requires $n \ge 3$ paired observations; otherwise returns `status = "InsufficientData"`.
2. **Bland–Altman Limits of Agreement**:
   $$\bar{d} = \frac{1}{n}\sum_{i=1}^n (A_i - B_i), \quad \text{LoA}_{95\%} = \bar{d} \pm 1.96 \cdot s_d$$
3. **Coefficient of Variation (`CV%`)**:
   $$\text{CV (\%)} = \frac{s}{\bar{x}} \times 100$$
