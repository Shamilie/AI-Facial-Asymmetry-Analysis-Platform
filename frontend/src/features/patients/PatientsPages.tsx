import React, { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  Grid2 as Grid,
  InputLabel,
  MenuItem,
  Pagination,
  Select,
  Step,
  StepLabel,
  Stepper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import SaveOutlinedIcon from '@mui/icons-material/SaveOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage, withAuthTokenUrl } from '@/services/api';
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  PatientContextHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { useAuthStore } from '@/store/authStore';
import { PatientSummary } from '@/types';

// ============================================================================
// PAGE 3 — Patient Listing
// ============================================================================

export const PatientListingPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const setActiveContext = useAuthStore((s) => s.setActiveContext);

  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [fractureSide, setFractureSide] = useState('');
  const [studyStatus, setStudyStatus] = useState('');
  const [analysisStatus, setAnalysisStatus] = useState('');
  const [enrolledFrom, setEnrolledFrom] = useState('');
  const [enrolledTo, setEnrolledTo] = useState('');
  const [sortBy, setSortBy] = useState('patient_code');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [
      'patients',
      search,
      fractureSide,
      studyStatus,
      analysisStatus,
      enrolledFrom,
      enrolledTo,
      sortBy,
      sortDir,
      page,
    ],
    queryFn: async () => {
      const params: Record<string, any> = { page, page_size: 15, sort_by: sortBy, sort_dir: sortDir };
      if (search.trim()) params.search = search.trim();
      if (fractureSide) params.fracture_side = fractureSide;
      if (studyStatus) params.study_status = studyStatus;
      if (analysisStatus) params.analysis_status = analysisStatus;
      if (enrolledFrom) params.enrolled_from = enrolledFrom;
      if (enrolledTo) params.enrolled_to = enrolledTo;
      const res = await api.get('/patients', { params });
      return res.data;
    },
  });

  const handleExport = (fmt: 'csv' | 'excel') => {
    window.open(withAuthTokenUrl(`/api/v1/patients/export?format=${fmt}`), '_blank');
  };

  if (isLoading) return <LoadingSkeleton rows={7} />;
  if (error) return <ErrorState message={extractErrorMessage(error)} onRetry={() => refetch()} />;

  const items: PatientSummary[] = data?.data || [];
  const meta = data?.meta || { total: 0, pages: 1 };

  return (
    <Box>
      <PageHeader
        title="Coded Patient Registry"
        subtitle="De-identified participant records for longitudinal unilateral mandibular fracture research"
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('csv')}
            >
              Export CSV
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('excel')}
            >
              Export Excel
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/patients/new')}
            >
              Add Patient
            </Button>
          </>
        }
      />

      <Card sx={{ mb: 2.5 }}>
        <CardContent>
          <Grid container spacing={1.5} alignItems="center">
            <Grid size={{ xs: 12, sm: 4, md: 2.5 }}>
              <TextField
                size="small"
                fullWidth
                label="Search Patient Code"
                placeholder="e.g. SYNTH-UMF-001"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 1.8 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Fracture Side</InputLabel>
                <Select
                  label="Fracture Side"
                  value={fractureSide}
                  onChange={(e) => setFractureSide(e.target.value)}
                >
                  <MenuItem value="">All Sides</MenuItem>
                  <MenuItem value="Left">Left</MenuItem>
                  <MenuItem value="Right">Right</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 1.8 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Visit / Study Status</InputLabel>
                <Select
                  label="Visit / Study Status"
                  value={studyStatus}
                  onChange={(e) => setStudyStatus(e.target.value)}
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="Enrolled">Enrolled</MenuItem>
                  <MenuItem value="Active">Active</MenuItem>
                  <MenuItem value="Completed">Completed</MenuItem>
                  <MenuItem value="Draft">Draft</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 1.8 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Analysis Status</InputLabel>
                <Select
                  label="Analysis Status"
                  value={analysisStatus}
                  onChange={(e) => setAnalysisStatus(e.target.value)}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="Completed">Completed</MenuItem>
                  <MenuItem value="ReviewRequired">Review Required</MenuItem>
                  <MenuItem value="Pending">Pending</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                size="small"
                type="date"
                fullWidth
                label="Enrolled From"
                InputLabelProps={{ shrink: true }}
                value={enrolledFrom}
                onChange={(e) => setEnrolledFrom(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2.1 }}>
              <TextField
                size="small"
                type="date"
                fullWidth
                label="Enrolled To"
                InputLabelProps={{ shrink: true }}
                value={enrolledTo}
                onChange={(e) => setEnrolledTo(e.target.value)}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {items.length === 0 ? (
        <EmptyState
          title="No coded patient records match the current filters"
          description="Clear your filters or register a new coded participant."
          actionLabel="Register Patient"
          onAction={() => navigate('/patients/new')}
        />
      ) : (
        <Card>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell
                    sx={{ cursor: 'pointer' }}
                    onClick={() => {
                      setSortBy('patient_code');
                      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
                    }}
                  >
                    Patient Code {sortBy === 'patient_code' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </TableCell>
                  <TableCell>Age</TableCell>
                  <TableCell>Sex</TableCell>
                  <TableCell>Fracture Side</TableCell>
                  <TableCell>Fracture Type</TableCell>
                  <TableCell>Surgery Date</TableCell>
                  <TableCell>Enrollment Date</TableCell>
                  <TableCell>Current Follow-up Stage</TableCell>
                  <TableCell>Analysis Status</TableCell>
                  <TableCell>Last Updated</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell>
                      <Stack direction="row" spacing={0.8} alignItems="center">
                        <Typography variant="body2" sx={{ fontWeight: 700, color: '#123B50' }}>
                          {p.patient_code}
                        </Typography>
                        {p.is_synthetic && (
                          <Chip
                            size="small"
                            label="SYNTHETIC DEMO"
                            sx={{ height: 18, fontSize: '0.62rem', bgcolor: '#FEF3C7', color: '#92400E', fontWeight: 700 }}
                          />
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>{p.age_at_enrollment ?? '—'}</TableCell>
                    <TableCell>{p.sex || 'NotCollected'}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={p.fracture_side || 'N/A'}
                        sx={{
                          fontWeight: 600,
                          bgcolor: p.fracture_side === 'Left' ? '#E0F2FE' : '#FCE7F3',
                          color: p.fracture_side === 'Left' ? '#075985' : '#9D174D',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ maxWidth: 230 }}>
                      <Typography variant="caption" sx={{ display: 'block' }} noWrap title={p.fracture_type || ''}>
                        {p.fracture_type || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>{p.surgery_date || '—'}</TableCell>
                    <TableCell>{p.enrollment_date || '—'}</TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {p.current_follow_up_stage} ({p.completed_visits_count}/{p.total_visits_count})
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={p.analysis_status} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(p.updated_at).toLocaleDateString()}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={0.8} justifyContent="flex-end">
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => {
                            setActiveContext({
                              patientId: p.id,
                              patientCode: p.patient_code,
                              fractureSide: p.fracture_side || undefined,
                              surgeryDate: p.surgery_date || undefined,
                              studyStatus: p.study_status,
                            });
                            navigate(`/patients/${p.id}`);
                          }}
                        >
                          Profile
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          color="secondary"
                          onClick={() => {
                            setActiveContext({
                              patientId: p.id,
                              patientCode: p.patient_code,
                              fractureSide: p.fracture_side || undefined,
                              surgeryDate: p.surgery_date || undefined,
                              studyStatus: p.study_status,
                            });
                            navigate(`/follow-up/${p.id}`);
                          }}
                        >
                          Follow-up
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Showing {items.length} of {meta.total} coded records
            </Typography>
            <Pagination
              count={meta.pages || 1}
              page={page}
              onChange={(_, val) => setPage(val)}
              color="primary"
              size="small"
            />
          </Box>
        </Card>
      )}
    </Box>
  );
};

// ============================================================================
// PAGE 4 — Patient Registration Wizard (6 Steps)
// ============================================================================

const WIZARD_STEPS = [
  '1. Identification & Consent',
  '2. Demographics',
  '3. Fracture Information',
  '4. Surgical Information',
  '5. Follow-up Schedule',
  '6. Review & Save',
];

function addDaysIso(baseDateStr: string, days: number): string {
  const d = new Date(baseDateStr || new Date().toISOString().slice(0, 10));
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export const PatientRegistrationPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setActiveContext = useAuthStore((s) => s.setActiveContext);

  const todayIso = new Date().toISOString().slice(0, 10);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Step 1
  const [patientCode, setPatientCode] = useState(`SYNTH-UMF-00${Math.floor(Math.random() * 20 + 7)}`);
  const [hospitalId, setHospitalId] = useState('DEMO-HOSP-2026');
  const [consentStatus, setConsentStatus] = useState('Obtained');
  const [consentDate, setConsentDate] = useState(todayIso);
  const [consentDocRef, setConsentDocRef] = useState('IRB-UMF-2026-SIGNED');
  const [enrollmentDate, setEnrollmentDate] = useState(todayIso);

  // Step 2
  const [ageAtEnrollment, setAgeAtEnrollment] = useState<number>(32);
  const [sex, setSex] = useState('Male');

  // Step 3
  const [fractureSide, setFractureSide] = useState<'Left' | 'Right'>('Left');
  const [fractureClassification, setFractureClassification] = useState('AO/OTA 91-B1 Displaced Unilateral Mandibular Angle Fracture');
  const [fractureLocation, setFractureLocation] = useState('Left mandibular angle and inferior border');
  const [injuryDate, setInjuryDate] = useState(addDaysIso(todayIso, -3));
  const [injuryMechanism, setInjuryMechanism] = useState('Road traffic accident (low-velocity fall)');
  const [associatedFractures, setAssociatedFractures] = useState('None (isolated unilateral fracture)');
  const [clinicalNotes, setClinicalNotes] = useState('Visible pre-operative left lower-facial contour asymmetry and mild trismus.');

  // Step 4
  const [surgeryDate, setSurgeryDate] = useState(addDaysIso(todayIso, 1));
  const [fixationType, setFixationType] = useState('ORIF — Two 2.0mm titanium miniplates (Champy line + inferior border)');
  const [surgicalApproach, setSurgicalApproach] = useState('Intraoral lower vestibular incision');
  const [plateDetails, setPlateDetails] = useState('2.0mm 4-hole and 6-hole titanium miniplates with 6mm monocortical screws');
  const [surgeonName, setSurgeonName] = useState('Dr. Marcus Thorne');
  const [operativeNotes, setOperativeNotes] = useState('Anatomical reduction under intermaxillary fixation; reproducible Class I occlusion.');

  // Step 5: Auto-computed 5 visits anchored on surgeryDate
  const defaultSchedule = useMemo(
    () => [
      { visit_type: 'PreOperative', label: 'Pre-operative', planned_date: addDaysIso(surgeryDate, -1), actual_date: todayIso },
      { visit_type: 'PostOp1Week', label: '1-week follow-up', planned_date: addDaysIso(surgeryDate, 7), actual_date: '' },
      { visit_type: 'PostOp6Weeks', label: '6-week follow-up', planned_date: addDaysIso(surgeryDate, 42), actual_date: '' },
      { visit_type: 'PostOp3Months', label: '3-month follow-up', planned_date: addDaysIso(surgeryDate, 90), actual_date: '' },
      { visit_type: 'PostOp6Months', label: '6-month follow-up', planned_date: addDaysIso(surgeryDate, 180), actual_date: '' },
    ],
    [surgeryDate, todayIso]
  );
  const [customSchedule, setCustomSchedule] = useState<typeof defaultSchedule | null>(null);
  const schedule = customSchedule || defaultSchedule;

  const validateStep = (step: number): string | null => {
    if (step === 0) {
      if (!patientCode.trim() || patientCode.trim().length < 3) return 'Patient research ID is required (min 3 characters).';
      if (!consentDocRef.trim()) return 'Consent document reference is required.';
    }
    if (step === 1) {
      if (!ageAtEnrollment || ageAtEnrollment < 1 || ageAtEnrollment > 120) return 'Enter a valid age at enrollment.';
    }
    if (step === 2) {
      if (!fractureClassification.trim() || !fractureLocation.trim()) return 'Fracture classification and location are required.';
    }
    if (step === 3) {
      if (!surgeryDate || !fixationType.trim()) return 'Surgery date and fixation type are required.';
    }
    return null;
  };

  const handleSubmit = async (isDraft: boolean) => {
    setError(null);
    if (!isDraft && consentStatus !== 'Obtained') {
      setError('Informed consent status must be "Obtained" before creating an active study record (or use Save Draft).');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/patients', {
        patient_code: patientCode.trim().toUpperCase(),
        hospital_id: hospitalId || null,
        age_at_enrollment: Number(ageAtEnrollment),
        sex,
        enrollment_date: enrollmentDate,
        is_draft: isDraft,
        is_synthetic: true,
        consent: {
          consent_status: consentStatus,
          consent_date: consentDate || null,
          consent_document_ref: consentDocRef,
        },
        fracture: {
          fracture_side: fractureSide,
          fracture_classification: fractureClassification,
          fracture_location: fractureLocation,
          injury_date: injuryDate || null,
          injury_mechanism: injuryMechanism,
          associated_fractures: associatedFractures,
          clinical_notes: clinicalNotes,
        },
        surgery: {
          surgery_date: surgeryDate,
          fixation_type: fixationType,
          surgical_approach: surgicalApproach,
          plate_details: plateDetails,
          surgeon_name: surgeonName,
          operative_notes: operativeNotes,
        },
        visit_schedule: schedule.map((s) => ({
          visit_type: s.visit_type,
          planned_date: s.planned_date || null,
          actual_date: s.actual_date || null,
        })),
      });
      const created = res.data.data;
      const firstVisitId = created.visits?.[0]?.id;
      setActiveContext({
        patientId: created.id,
        patientCode: created.patient_code,
        fractureSide,
        surgeryDate,
        studyStatus: created.study_status,
        visitId: firstVisitId,
        visitType: 'PreOperative',
      });
      await queryClient.invalidateQueries({ queryKey: ['patients'] });
      navigate(`/patients/${created.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box>
      <PageHeader
        title="Patient Registration Wizard"
        subtitle="Enroll a coded participant under Protocol UMF-ASYM-2026 and auto-generate the 5 longitudinal study visits"
      />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stepper activeStep={activeStep} alternativeLabel>
            {WIZARD_STEPS.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent sx={{ p: 3 }}>
          {activeStep === 0 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12 }}>
                <Alert severity="info">
                  Use coded research identifiers (e.g., <b>SYNTH-UMF-007</b>). Do not enter patient full names.
                </Alert>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Patient Research ID (Coded)"
                  fullWidth
                  required
                  value={patientCode}
                  onChange={(e) => setPatientCode(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Hospital ID (Protocol-Permitted Cross-Reference)"
                  fullWidth
                  value={hospitalId}
                  onChange={(e) => setHospitalId(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <FormControl fullWidth>
                  <InputLabel>Consent Status</InputLabel>
                  <Select
                    label="Consent Status"
                    value={consentStatus}
                    onChange={(e) => setConsentStatus(e.target.value)}
                  >
                    <MenuItem value="Obtained">Obtained</MenuItem>
                    <MenuItem value="Pending">Pending</MenuItem>
                    <MenuItem value="Declined">Declined</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Consent Date"
                  type="date"
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                  value={consentDate}
                  onChange={(e) => setConsentDate(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Enrollment Date"
                  type="date"
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                  value={enrollmentDate}
                  onChange={(e) => setEnrollmentDate(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <TextField
                  label="Consent Document Reference / IRB Form ID"
                  fullWidth
                  required
                  value={consentDocRef}
                  onChange={(e) => setConsentDocRef(e.target.value)}
                />
              </Grid>
            </Grid>
          )}

          {activeStep === 1 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12 }}>
                <Alert severity="info">
                  Data minimization applied: only protocol-approved demographic variables are collected.
                </Alert>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Age at Enrollment (Years)"
                  type="number"
                  fullWidth
                  required
                  value={ageAtEnrollment}
                  onChange={(e) => setAgeAtEnrollment(Number(e.target.value))}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <FormControl fullWidth>
                  <InputLabel>Sex (Protocol Approved)</InputLabel>
                  <Select label="Sex (Protocol Approved)" value={sex} onChange={(e) => setSex(e.target.value)}>
                    <MenuItem value="Male">Male</MenuItem>
                    <MenuItem value="Female">Female</MenuItem>
                    <MenuItem value="Other">Other</MenuItem>
                    <MenuItem value="NotCollected">Not Collected</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          )}

          {activeStep === 2 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 4 }}>
                <FormControl fullWidth>
                  <InputLabel>Unilateral Fracture Side</InputLabel>
                  <Select
                    label="Unilateral Fracture Side"
                    value={fractureSide}
                    onChange={(e) => setFractureSide(e.target.value as 'Left' | 'Right')}
                  >
                    <MenuItem value="Left">Left</MenuItem>
                    <MenuItem value="Right">Right</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Injury Date"
                  type="date"
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                  value={injuryDate}
                  onChange={(e) => setInjuryDate(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Fracture Location"
                  fullWidth
                  required
                  value={fractureLocation}
                  onChange={(e) => setFractureLocation(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Fracture Classification (e.g. AO/OTA)"
                  fullWidth
                  required
                  value={fractureClassification}
                  onChange={(e) => setFractureClassification(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Injury Mechanism"
                  fullWidth
                  value={injuryMechanism}
                  onChange={(e) => setInjuryMechanism(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <TextField
                  label="Associated Fractures"
                  fullWidth
                  value={associatedFractures}
                  onChange={(e) => setAssociatedFractures(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <TextField
                  label="Clinical Notes"
                  fullWidth
                  multiline
                  rows={2}
                  value={clinicalNotes}
                  onChange={(e) => setClinicalNotes(e.target.value)}
                />
              </Grid>
            </Grid>
          )}

          {activeStep === 3 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Surgery Date"
                  type="date"
                  fullWidth
                  required
                  InputLabelProps={{ shrink: true }}
                  value={surgeryDate}
                  onChange={(e) => {
                    setSurgeryDate(e.target.value);
                    setCustomSchedule(null);
                  }}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Surgeon / Examiner"
                  fullWidth
                  value={surgeonName}
                  onChange={(e) => setSurgeonName(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Surgical Approach"
                  fullWidth
                  value={surgicalApproach}
                  onChange={(e) => setSurgicalApproach(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Fixation Type"
                  fullWidth
                  required
                  value={fixationType}
                  onChange={(e) => setFixationType(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  label="Plate & Screw Details"
                  fullWidth
                  value={plateDetails}
                  onChange={(e) => setPlateDetails(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <TextField
                  label="Operative Notes"
                  fullWidth
                  multiline
                  rows={2}
                  value={operativeNotes}
                  onChange={(e) => setOperativeNotes(e.target.value)}
                />
              </Grid>
            </Grid>
          )}

          {activeStep === 4 && (
            <Box>
              <Alert severity="info" sx={{ mb: 2 }}>
                The 5 longitudinal protocol visits are automatically generated from the surgery date ({surgeryDate}).
                Authorized coordinators may adjust planned or actual visit dates below.
              </Alert>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Visit Stage</TableCell>
                      <TableCell>Protocol Window</TableCell>
                      <TableCell>Planned Date</TableCell>
                      <TableCell>Actual Date (Optional)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {schedule.map((row, idx) => (
                      <TableRow key={row.visit_type}>
                        <TableCell sx={{ fontWeight: 700 }}>{row.label}</TableCell>
                        <TableCell>{row.visit_type}</TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="date"
                            value={row.planned_date}
                            onChange={(e) => {
                              const next = [...schedule];
                              next[idx] = { ...next[idx], planned_date: e.target.value };
                              setCustomSchedule(next);
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="date"
                            value={row.actual_date}
                            onChange={(e) => {
                              const next = [...schedule];
                              next[idx] = { ...next[idx], actual_date: e.target.value };
                              setCustomSchedule(next);
                            }}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {activeStep === 5 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>
                Complete Registration Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                        Identification, Consent & Demographics
                      </Typography>
                      <Typography variant="body2"><b>Patient Code:</b> {patientCode}</Typography>
                      <Typography variant="body2"><b>Consent:</b> {consentStatus} ({consentDate}) — {consentDocRef}</Typography>
                      <Typography variant="body2"><b>Enrollment Date:</b> {enrollmentDate}</Typography>
                      <Typography variant="body2"><b>Age / Sex:</b> {ageAtEnrollment} yrs / {sex}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                        Fracture & Fixation Details
                      </Typography>
                      <Typography variant="body2"><b>Fracture Side:</b> {fractureSide}</Typography>
                      <Typography variant="body2"><b>Classification:</b> {fractureClassification}</Typography>
                      <Typography variant="body2"><b>Location:</b> {fractureLocation}</Typography>
                      <Typography variant="body2"><b>Surgery Date:</b> {surgeryDate}</Typography>
                      <Typography variant="body2"><b>Fixation:</b> {fixationType}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Box>
          )}

          <Divider sx={{ my: 3 }} />

          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Button
              disabled={activeStep === 0 || submitting}
              onClick={() => setActiveStep((s) => s - 1)}
            >
              Previous
            </Button>

            <Stack direction="row" spacing={1.5}>
              <Button
                variant="outlined"
                startIcon={<SaveOutlinedIcon />}
                disabled={submitting}
                onClick={() => handleSubmit(true)}
              >
                Save Draft
              </Button>
              {activeStep < WIZARD_STEPS.length - 1 ? (
                <Button
                  variant="contained"
                  endIcon={<ArrowForwardIcon />}
                  onClick={() => {
                    const err = validateStep(activeStep);
                    if (err) {
                      setError(err);
                      return;
                    }
                    setError(null);
                    setActiveStep((s) => s + 1);
                  }}
                >
                  Next Step
                </Button>
              ) : (
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<CheckCircleOutlineIcon />}
                  disabled={submitting}
                  onClick={() => handleSubmit(false)}
                >
                  {submitting ? 'Creating Patient...' : 'Create Patient & 5 Study Visits'}
                </Button>
              )}
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

// ============================================================================
// PAGE 5 — Patient Profile Workspace (9 Tabs)
// ============================================================================

export const PatientProfilePage: React.FC = () => {
  const params = useParams<{ patientId?: string; id?: string }>();
  const navigate = useNavigate();
  const activePatientId = useAuthStore((s) => s.activeContext.patientId);
  const setActiveContext = useAuthStore((s) => s.setActiveContext);
  const id = params.patientId || params.id || activePatientId;
  const [tab, setTab] = useState(0);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['patient-overview', id],
    enabled: Boolean(id),
    queryFn: async () => {
      let targetId = id;
      if (!targetId || targetId === 'undefined') {
        const listRes = await api.get('/patients?page=1&page_size=1');
        const listData = listRes.data.data;
        const items = Array.isArray(listData) ? listData : listData?.items || [];
        targetId = items[0]?.id;
      }
      if (!targetId) {
        throw new Error('No patient record found.');
      }
      const res = await api.get(`/patients/${targetId}/overview`);
      const d = res.data.data;
      const firstVisit = d.visits?.[0];
      setActiveContext({
        patientId: d.id,
        patientCode: d.patient_code,
        fractureSide: d.fracture_side,
        surgeryDate: d.surgery_date,
        studyStatus: d.study_status,
        visitId: firstVisit?.id,
        visitType: firstVisit?.visit_type,
      });
      return d;
    },
  });

  if (isLoading) return <LoadingSkeleton rows={7} />;
  if (error || !data) return <ErrorState message={extractErrorMessage(error)} onRetry={() => refetch()} />;

  const visits: any[] = data.visits || [];
  const primaryVisit = visits[0];

  return (
    <Box>
      <PatientContextHeader
        patientId={data.id}
        patientCode={data.patient_code}
        fractureSide={data.fracture_side}
        surgeryDate={data.surgery_date}
        studyStatus={data.study_status}
        visitId={primaryVisit?.id}
        visitType={primaryVisit?.visit_type}
        isSynthetic={data.is_synthetic}
      />
      <ResearchDisclaimerBanner compact />

      <Card sx={{ mb: 2.5 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: '1px solid #E2E8F0', px: 2 }}
        >
          <Tab label="1. Overview" />
          <Tab label="2. Clinical Details" />
          <Tab label="3. Visits & Images" />
          <Tab label="4. AI Analysis" />
          <Tab label="5. 3D Reconstruction" />
          <Tab label="6. Measurements" />
          <Tab label="7. Follow-up Comparison" />
          <Tab label="8. Reports" />
          <Tab label="9. Audit History" />
        </Tabs>

        <CardContent sx={{ p: 3 }}>
          {tab === 0 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 4 }}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Participant & Consent Summary
                    </Typography>
                    <Typography variant="body2"><b>Patient Code:</b> {data.patient_code}</Typography>
                    <Typography variant="body2"><b>Age at Enrollment:</b> {data.age_at_enrollment ?? '—'}</Typography>
                    <Typography variant="body2"><b>Sex:</b> {data.sex}</Typography>
                    <Typography variant="body2"><b>Enrollment Date:</b> {data.enrollment_date}</Typography>
                    <Typography variant="body2"><b>Consent Status:</b> {data.consent_status}</Typography>
                    <Typography variant="body2"><b>Consent Ref:</b> {data.consent?.consent_document_ref || 'On file'}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, md: 4 }}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Fracture & Surgical Summary
                    </Typography>
                    <Typography variant="body2"><b>Fracture Side:</b> {data.fracture_side}</Typography>
                    <Typography variant="body2"><b>Classification:</b> {data.fracture_detail?.fracture_classification}</Typography>
                    <Typography variant="body2"><b>Location:</b> {data.fracture_detail?.fracture_location}</Typography>
                    <Typography variant="body2"><b>Surgery Date:</b> {data.surgery_date}</Typography>
                    <Typography variant="body2"><b>Fixation:</b> {data.surgery_detail?.fixation_type}</Typography>
                    <Typography variant="body2"><b>Surgeon:</b> {data.surgery_detail?.surgeon_name}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, md: 4 }}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Pending Study Tasks
                    </Typography>
                    {(data.pending_tasks || []).length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        All scheduled tasks up to date.
                      </Typography>
                    ) : (
                      <Stack spacing={1}>
                        {data.pending_tasks.map((t: any, i: number) => (
                          <Alert
                            key={i}
                            severity="warning"
                            action={
                              <Button
                                size="small"
                                onClick={() =>
                                  navigate(
                                    t.type === 'image_upload'
                                      ? `/visits/${t.visit_id}/images`
                                      : `/measurements/${t.visit_id}`
                                  )
                                }
                              >
                                Open
                              </Button>
                            }
                          >
                            {t.message}
                          </Alert>
                        ))}
                      </Stack>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  Longitudinal Visit Completion Timeline
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Visit Stage</TableCell>
                        <TableCell>Planned Date</TableCell>
                        <TableCell>Actual Date</TableCell>
                        <TableCell>Images</TableCell>
                        <TableCell>Measurements (Approved)</TableCell>
                        <TableCell>3D Mesh</TableCell>
                        <TableCell>Visit Status</TableCell>
                        <TableCell align="right">Workspace Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {visits.map((v) => (
                        <TableRow key={v.id} hover>
                          <TableCell sx={{ fontWeight: 700 }}>{v.label}</TableCell>
                          <TableCell>{v.planned_date || '—'}</TableCell>
                          <TableCell>{v.actual_date || '—'}</TableCell>
                          <TableCell>{v.image_count}/4 views</TableCell>
                          <TableCell>
                            {v.approved_measurement_count}/{v.measurement_count}
                          </TableCell>
                          <TableCell>{v.has_3d_mesh ? 'Available' : '—'}</TableCell>
                          <TableCell>
                            <StatusBadge status={v.status} />
                          </TableCell>
                          <TableCell align="right">
                            <Stack direction="row" spacing={0.8} justifyContent="flex-end">
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => {
                                  setActiveContext({ visitId: v.id, visitType: v.visit_type });
                                  navigate(`/visits/${v.id}/images`);
                                }}
                              >
                                Images
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => {
                                  setActiveContext({ visitId: v.id, visitType: v.visit_type });
                                  navigate(`/ai-analysis/${v.id}`);
                                }}
                              >
                                AI
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => {
                                  setActiveContext({ visitId: v.id, visitType: v.visit_type });
                                  navigate(`/landmarks/${v.id}`);
                                }}
                              >
                                Landmarks
                              </Button>
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => {
                                  setActiveContext({ visitId: v.id, visitType: v.visit_type });
                                  navigate(`/measurements/${v.id}`);
                                }}
                              >
                                Measurements
                              </Button>
                            </Stack>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Grid>
            </Grid>
          )}

          {tab === 1 && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  Fracture Information
                </Typography>
                <Typography variant="body2"><b>Fracture Side:</b> {data.fracture_detail?.fracture_side}</Typography>
                <Typography variant="body2"><b>Classification:</b> {data.fracture_detail?.fracture_classification}</Typography>
                <Typography variant="body2"><b>Anatomical Location:</b> {data.fracture_detail?.fracture_location}</Typography>
                <Typography variant="body2"><b>Injury Date:</b> {data.fracture_detail?.injury_date || '—'}</Typography>
                <Typography variant="body2"><b>Mechanism:</b> {data.fracture_detail?.injury_mechanism || '—'}</Typography>
                <Typography variant="body2"><b>Associated Fractures:</b> {data.fracture_detail?.associated_fractures || '—'}</Typography>
                <Typography variant="body2" sx={{ mt: 1 }}><b>Clinical Notes:</b> {data.fracture_detail?.clinical_notes || '—'}</Typography>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  Surgical Fixation Information
                </Typography>
                <Typography variant="body2"><b>Surgery Date:</b> {data.surgery_detail?.surgery_date}</Typography>
                <Typography variant="body2"><b>Fixation Type:</b> {data.surgery_detail?.fixation_type}</Typography>
                <Typography variant="body2"><b>Surgical Approach:</b> {data.surgery_detail?.surgical_approach}</Typography>
                <Typography variant="body2"><b>Plate Details:</b> {data.surgery_detail?.plate_details}</Typography>
                <Typography variant="body2"><b>Surgeon:</b> {data.surgery_detail?.surgeon_name}</Typography>
                <Typography variant="body2" sx={{ mt: 1 }}><b>Operative Notes:</b> {data.surgery_detail?.operative_notes}</Typography>
              </Grid>
            </Grid>
          )}

          {tab === 2 && (
            <Stack spacing={1.5}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Study Visits & Image Collection
              </Typography>
              {visits.map((v) => (
                <Card key={v.id} variant="outlined">
                  <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                        {v.label} ({v.visit_type})
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Planned: {v.planned_date} | Actual: {v.actual_date || 'Pending'} | Uploaded Views: {v.image_count}/4
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1}>
                      <StatusBadge status={v.status} />
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => navigate(`/visits/${v.id}/images`)}
                      >
                        Open Image Workspace
                      </Button>
                    </Stack>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          )}

          {tab === 3 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                AI Analysis Pipeline Per Visit
              </Typography>
              <Stack spacing={1.2}>
                {visits.map((v) => (
                  <Card key={v.id} variant="outlined">
                    <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {v.label} — {v.image_count} images uploaded
                      </Typography>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => navigate(`/ai-analysis/${v.id}`)}
                      >
                        Open 11-Stage AI Workspace
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            </Box>
          )}

          {tab === 4 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                3D Face Reconstruction Workspace
              </Typography>
              <Stack spacing={1.2}>
                {visits.map((v) => (
                  <Card key={v.id} variant="outlined">
                    <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {v.label} — 3D Mesh: {v.has_3d_mesh ? 'Generated' : 'Not yet generated'}
                      </Typography>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => navigate(`/reconstruction/${v.id}`)}
                      >
                        Open 3D Viewer
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            </Box>
          )}

          {tab === 5 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                Quantitative Asymmetry Measurements
              </Typography>
              <Stack spacing={1.2}>
                {visits.map((v) => (
                  <Card key={v.id} variant="outlined">
                    <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {v.label} — {v.approved_measurement_count}/{v.measurement_count} approved
                      </Typography>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => navigate(`/measurements/${v.id}`)}
                      >
                        Open Measurements
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            </Box>
          )}

          {tab === 6 && (
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                Longitudinal 5-Visit Asymmetry Comparison
              </Typography>
              <Button
                variant="contained"
                color="secondary"
                onClick={() => navigate(`/follow-up/${data.id}`)}
              >
                Launch Full Follow-up Comparison Workspace
              </Button>
            </Box>
          )}

          {tab === 7 && (
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  Generated Patient Research Reports
                </Typography>
                <Button variant="contained" size="small" onClick={() => navigate('/reports')}>
                  Open Report Center
                </Button>
              </Stack>
              {(data.recent_reports || []).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No reports generated yet for this patient.
                </Typography>
              ) : (
                <Stack spacing={1}>
                  {data.recent_reports.map((r: any) => (
                    <Card key={r.id} variant="outlined">
                      <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>{r.title}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(r.created_at).toLocaleString()}
                          </Typography>
                        </Box>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() =>
                            window.open(withAuthTokenUrl(`/api/v1/reports/${r.id}/download?format=PDF`), '_blank')
                          }
                        >
                          Download PDF
                        </Button>
                      </CardContent>
                    </Card>
                  ))}
                </Stack>
              )}
            </Box>
          )}

          {tab === 8 && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                Patient Audit Trail
              </Typography>
              {(data.audit_history || []).map((a: any) => (
                <Box
                  key={a.id}
                  sx={{ p: 1.2, mb: 1, borderRadius: 1, bgcolor: '#F8FAFC', border: '1px solid #E2E8F0' }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {a.action} — {a.user_email}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(a.created_at).toLocaleString()} {a.reason ? `| ${a.reason}` : ''}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};
