export interface UserProfile {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  roles: string[];
  primary_role: string;
  permissions: string[];
}

export interface PatientSummary {
  id: string;
  patient_code: string;
  hospital_id?: string | null;
  age_at_enrollment?: number | null;
  sex?: string;
  fracture_side?: 'Right' | 'Left' | null;
  fracture_type?: string | null;
  fracture_location?: string | null;
  surgery_date?: string | null;
  fixation_type?: string | null;
  surgeon_name?: string | null;
  enrollment_date?: string | null;
  study_status: string;
  consent_status: string;
  current_follow_up_stage: string;
  completed_visits_count: number;
  total_visits_count: number;
  analysis_status: string;
  is_synthetic: boolean;
  updated_at: string;
}

export interface VisitSummary {
  id: string;
  patient_id: string;
  patient_code?: string;
  fracture_side?: string;
  visit_type: string;
  label?: string;
  planned_date?: string | null;
  actual_date?: string | null;
  status: string;
  image_count: number;
  image_upload_status?: string;
  ai_analysis_status?: string;
  examiner_review_status?: string;
  measurement_count: number;
  approved_measurement_count: number;
  completion_status?: string;
  has_3d_mesh?: boolean;
  notes?: string | null;
  surgery_date?: string | null;
  study_status?: string | null;
  clinical_assessment?: Record<string, any> | null;
}

export interface QualityResult {
  id: string;
  provider?: string;
  model_name?: string;
  model_version?: string;
  overall_score?: number | null;
  status: 'Pass' | 'Warning' | 'Fail';
  face_visibility?: { status: string; value: any; message: string } | null;
  orientation_check?: { status: string; value: any; message: string } | null;
  lighting_check?: { status: string; value: any; message: string } | null;
  blur_check?: { status: string; value: any; message: string } | null;
  occlusion_check?: { status: string; value: any; message: string } | null;
  framing_check?: { status: string; value: any; message: string } | null;
  resolution_check?: { status: string; value: any; message: string } | null;
  issues: string[];
  suggestions: string[];
  manual_override_status?: 'Accepted' | 'Rejected' | null;
  manual_override_at?: string | null;
  disclaimer?: string;
}

export interface VisitImageRecord {
  id: string;
  visit_id: string;
  image_type: 'Frontal' | 'RightLateral' | 'LeftLateral' | 'OPG';
  original_filename: string;
  file_size?: number;
  mime_type?: string;
  width?: number;
  height?: number;
  capture_date?: string | null;
  device_metadata?: Record<string, any> | null;
  upload_status: string;
  acceptance_status: 'Pending' | 'Accepted' | 'Rejected';
  is_synthetic: boolean;
  file_url: string;
  created_at: string;
  quality_result?: QualityResult | null;
}

export interface AIStageJob {
  id: string | null;
  visit_id: string;
  patient_id?: string;
  patient_code?: string;
  visit_type?: string;
  pipeline_run_id?: string | null;
  stage_order: number;
  task_type: string;
  stage_label: string;
  provider: string;
  model_name?: string | null;
  model_version?: string | null;
  is_demo: boolean;
  status: string;
  attempt?: number;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  warnings: string[];
  error_message?: string | null;
  output?: Record<string, any> | null;
}

export interface LandmarkRecord {
  id: string;
  image_id: string;
  landmark_definition_id: string;
  code: string;
  name: string;
  side: string;
  anatomical_region: string;
  landmark_type: 'Facial' | 'OPG';
  source: string;
  predicted_x: number | null;
  predicted_y: number | null;
  examiner_x: number | null;
  examiner_y: number | null;
  effective_x: number | null;
  effective_y: number | null;
  z?: number | null;
  confidence?: number | null;
  status: string;
  state_category: 'AIPredicted' | 'ExaminerReviewed' | 'Approved';
  model_name?: string | null;
  model_version?: string | null;
  reviews: Array<{
    id: string;
    reviewer_email: string;
    original_x: number | null;
    original_y: number | null;
    corrected_x: number | null;
    corrected_y: number | null;
    review_status: string;
    correction_reason?: string;
    reviewed_at: string;
  }>;
}

export interface CalibrationItem {
  id: string;
  visit_id: string;
  image_id?: string | null;
  calibration_type: 'FrontalPhoto' | 'RightLateralPhoto' | 'LeftLateralPhoto' | 'OPG';
  reference_marker_type: string;
  known_marker_length_mm: number;
  measured_marker_length_px: number;
  mm_per_pixel: number;
  pixels_per_mm?: number;
  marker_location?: string;
  calibration_plane?: string;
  calibration_method?: string;
  magnification_factor?: number | null;
  pixel_spacing_x?: number | null;
  pixel_spacing_y?: number | null;
  regional_calibration?: Record<string, any> | null;
  is_physical: boolean;
  same_plane_confirmed: boolean;
  is_active: boolean;
  version: number;
  warnings: string[];
  calibrated_by_email?: string;
  calibration_date?: string;
  notes?: string;
}

export interface MeasurementItem {
  id: string;
  visit_id: string;
  code: string;
  name: string;
  description: string;
  measurement_type: string;
  formula: string;
  right_value: number | null;
  left_value: number | null;
  absolute_difference: number | null;
  asymmetry_index: number | null;
  unit: string;
  source_image_type: string;
  calibration_id?: string | null;
  calibration_reference: string;
  landmark_refs: Record<string, any>;
  method: 'AIPredicted' | 'ExaminerReviewed' | 'Validated';
  model_name?: string | null;
  model_version?: string | null;
  status: string;
  is_unscaled: boolean;
  version: number;
  warnings: string[];
  notes?: string | null;
  reviewer_notes?: string | null;
  latest_approval?: {
    approver_email: string;
    approval_status: string;
    comments?: string;
    approved_at: string;
  } | null;
}
