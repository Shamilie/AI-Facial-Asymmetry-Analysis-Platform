import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid2 as Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import EditCalendarIcon from '@mui/icons-material/EditCalendar';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage, withAuthTokenUrl } from '@/services/api';
import {
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  PatientContextHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { useAuthStore } from '@/store/authStore';
import { VisitImageRecord, VisitSummary } from '@/types';

const VISIT_STATUS_OPTIONS = [
  'Planned',
  'Scheduled',
  'InProgress',
  'ImagesPending',
  'Processing',
  'ReviewRequired',
  'Completed',
  'Missed',
  'Cancelled',
];

// ============================================================================
// PAGE 6 — Visit Management
// ============================================================================

export const VisitManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setActiveContext = useAuthStore((s) => s.setActiveContext);

  const [statusFilter, setStatusFilter] = useState('');
  const [visitTypeFilter, setVisitTypeFilter] = useState('');
  const [editVisit, setEditVisit] = useState<VisitSummary | null>(null);
  const [editActualDate, setEditActualDate] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);

  const { data: visits = [], isLoading, error, refetch } = useQuery({
    queryKey: ['visits', statusFilter, visitTypeFilter],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (visitTypeFilter) params.visit_type = visitTypeFilter;
      const res = await api.get('/visits', { params });
      return res.data.data as VisitSummary[];
    },
  });

  const handleSaveVisit = async () => {
    if (!editVisit) return;
    setSaveError(null);
    try {
      await api.patch(`/visits/${editVisit.id}`, {
        actual_date: editActualDate || null,
        status: editStatus,
        notes: editNotes,
        reason: 'Updated visit schedule/status from Visit Management',
      });
      setEditVisit(null);
      await queryClient.invalidateQueries({ queryKey: ['visits'] });
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    }
  };

  if (isLoading) return <LoadingSkeleton rows={7} />;
  if (error) return <ErrorState message={extractErrorMessage(error)} onRetry={() => refetch()} />;

  return (
    <Box>
      <PageHeader
        title="Longitudinal Study Visit Management"
        subtitle="Track Pre-operative, 1-week, 6-week, 3-month, and 6-month visits across all enrolled participants"
      />

      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>Protocol Governance Rule:</strong> A visit is never marked <b>Completed</b> solely because AI image processing has finished; examiner measurement review and approval are mandatory prerequisites.
      </Alert>

      <Card sx={{ mb: 2.5 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel>Filter by Visit Type</InputLabel>
              <Select
                label="Filter by Visit Type"
                value={visitTypeFilter}
                onChange={(e) => setVisitTypeFilter(e.target.value)}
              >
                <MenuItem value="">All 5 Protocol Visits</MenuItem>
                <MenuItem value="PreOperative">Pre-operative</MenuItem>
                <MenuItem value="PostOp1Week">Post-op – 1 week</MenuItem>
                <MenuItem value="PostOp6Weeks">Post-op – 6 weeks</MenuItem>
                <MenuItem value="PostOp3Months">Post-op – 3 months</MenuItem>
                <MenuItem value="PostOp6Months">Post-op – 6 months</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel>Filter by Visit Status</InputLabel>
              <Select
                label="Filter by Visit Status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="">All Statuses</MenuItem>
                {VISIT_STATUS_OPTIONS.map((st) => (
                  <MenuItem key={st} value={st}>
                    {st}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Patient Code</TableCell>
                <TableCell>Visit Type</TableCell>
                <TableCell>Planned Date</TableCell>
                <TableCell>Actual Date</TableCell>
                <TableCell>Visit Status</TableCell>
                <TableCell>Image Upload</TableCell>
                <TableCell>AI Analysis</TableCell>
                <TableCell>Examiner Review</TableCell>
                <TableCell>Completion</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visits.map((v) => (
                <TableRow key={v.id} hover>
                  <TableCell sx={{ fontWeight: 700, color: '#123B50' }}>{v.patient_code}</TableCell>
                  <TableCell>{v.visit_type}</TableCell>
                  <TableCell>{v.planned_date || '—'}</TableCell>
                  <TableCell>{v.actual_date || '—'}</TableCell>
                  <TableCell>
                    <StatusBadge status={v.status} />
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={v.image_upload_status}
                      color={v.image_count >= 4 ? 'success' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={v.ai_analysis_status} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={v.examiner_review_status} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={v.completion_status} />
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.8} justifyContent="flex-end">
                      <Button
                        size="small"
                        startIcon={<EditCalendarIcon fontSize="small" />}
                        onClick={() => {
                          setEditVisit(v);
                          setEditActualDate(v.actual_date || '');
                          setEditStatus(v.status);
                          setEditNotes(v.notes || '');
                          setSaveError(null);
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          setActiveContext({
                            patientId: v.patient_id,
                            patientCode: v.patient_code,
                            fractureSide: v.fracture_side,
                            visitId: v.id,
                            visitType: v.visit_type,
                          });
                          navigate(`/visits/${v.id}/images`);
                        }}
                      >
                        Images
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => {
                          setActiveContext({
                            patientId: v.patient_id,
                            patientCode: v.patient_code,
                            fractureSide: v.fracture_side,
                            visitId: v.id,
                            visitType: v.visit_type,
                          });
                          navigate(`/ai-analysis/${v.id}`);
                        }}
                      >
                        Analyze
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      <Dialog open={Boolean(editVisit)} onClose={() => setEditVisit(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Update Visit — {editVisit?.patient_code} ({editVisit?.visit_type})
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {saveError && <Alert severity="error">{saveError}</Alert>}
            <TextField
              label="Actual Visit Date"
              type="date"
              size="small"
              fullWidth
              InputLabelProps={{ shrink: true }}
              value={editActualDate}
              onChange={(e) => setEditActualDate(e.target.value)}
            />
            <FormControl size="small" fullWidth>
              <InputLabel>Visit Status</InputLabel>
              <Select
                label="Visit Status"
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value)}
              >
                {VISIT_STATUS_OPTIONS.map((st) => (
                  <MenuItem key={st} value={st}>
                    {st}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Visit Notes"
              size="small"
              fullWidth
              multiline
              rows={2}
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditVisit(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveVisit}>
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 7 — Image Acquisition and Upload (4 Panels + Quality AI Assessment)
// ============================================================================

const FOUR_VIEWS: Array<{
  type: 'Frontal' | 'RightLateral' | 'LeftLateral' | 'OPG';
  title: string;
  protocolHint: string;
}> = [
  {
    type: 'Frontal',
    title: '1. Standardized Frontal Facial Photograph',
    protocolHint: 'Natural head position, Frankfort horizontal parallel to floor, neutral expression, fiducial scale ruler in coronal facial plane.',
  },
  {
    type: 'RightLateral',
    title: '2. Right Lateral Facial Photograph',
    protocolHint: 'True 90° right profile, ear & Tragion unobstructed, fiducial scale ruler in mid-sagittal plane.',
  },
  {
    type: 'LeftLateral',
    title: '3. Left Lateral Facial Photograph',
    protocolHint: 'True 90° left profile, ear & Tragion unobstructed, fiducial scale ruler in mid-sagittal plane.',
  },
  {
    type: 'OPG',
    title: '4. Orthopantomogram (OPG)',
    protocolHint: 'Standard panoramic radiograph covering bilateral condyles, rami, gonial angles, and mandibular symphysis.',
  },
];

export const ImageAcquisitionPage: React.FC = () => {
  const params = useParams<{ visitId?: string; id?: string }>();
  const routeVisitId = params.visitId || params.id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeContext, setActiveContext } = useAuthStore();

  const [selectedVisitId, setSelectedVisitId] = useState<string>(routeVisitId || activeContext.visitId || '');
  const [busyView, setBusyView] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (routeVisitId) setSelectedVisitId(routeVisitId);
  }, [routeVisitId]);

  const { data: allVisits = [] } = useQuery({
    queryKey: ['visits-selector'],
    queryFn: async () => {
      const res = await api.get('/visits');
      const list = res.data.data as VisitSummary[];
      if (!selectedVisitId && list.length > 0) {
        setSelectedVisitId(list[0].id);
      }
      return list;
    },
  });

  const activeVisitId = selectedVisitId || allVisits[0]?.id || '';

  const { data: visitDetail } = useQuery({
    queryKey: ['visit-detail', activeVisitId],
    enabled: Boolean(activeVisitId),
    queryFn: async () => {
      const res = await api.get(`/visits/${activeVisitId}`);
      const d = res.data.data;
      setActiveContext({
        patientId: d.patient_id,
        patientCode: d.patient_code,
        fractureSide: d.fracture_side,
        surgeryDate: d.surgery_date,
        studyStatus: d.study_status,
        visitId: d.id,
        visitType: d.visit_type,
      });
      return d;
    },
  });

  const { data: images = [], isLoading, refetch } = useQuery({
    queryKey: ['visit-images', activeVisitId],
    enabled: Boolean(activeVisitId),
    queryFn: async () => {
      const res = await api.get(`/visits/${activeVisitId}/images`);
      return res.data.data as VisitImageRecord[];
    },
  });

  const byType = new Map<string, VisitImageRecord>();
  for (const im of images) {
    byType.set(im.image_type, im);
  }

  const handleFileUpload = async (viewType: string, file: File) => {
    if (!activeVisitId) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    setBusyView(viewType);
    try {
      const form = new FormData();
      form.append('image_type', viewType);
      form.append('replace_existing', 'true');
      form.append('file', file);
      await api.post(`/visits/${activeVisitId}/images`, form);
      setSuccessMsg(`${viewType} uploaded and quality-screened.`);
      await refetch();
      await queryClient.invalidateQueries({ queryKey: ['visits'] });
    } catch (err) {
      setErrorMsg(extractErrorMessage(err));
    } finally {
      setBusyView(null);
    }
  };

  const handleGenerateSyntheticSet = async () => {
    if (!activeVisitId) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    setBusyView('ALL');
    try {
      await api.post(`/visits/${activeVisitId}/images/generate-synthetic`);
      setSuccessMsg('Generated all 4 standardized SYNTHETIC demo views and view-specific calibrations.');
      await refetch();
    } catch (err) {
      setErrorMsg(extractErrorMessage(err));
    } finally {
      setBusyView(null);
    }
  };

  const handleManualDecision = async (imageId: string, decision: 'Accepted' | 'Rejected') => {
    setErrorMsg(null);
    try {
      await api.post(`/images/${imageId}/quality-override`, {
        decision,
        reason: `Examiner manual ${decision.toLowerCase()} in Image Acquisition workspace`,
      });
      await refetch();
    } catch (err) {
      setErrorMsg(extractErrorMessage(err));
    }
  };

  const handleDeleteImage = async (imageId: string) => {
    setErrorMsg(null);
    try {
      await api.delete(`/images/${imageId}`);
      await refetch();
    } catch (err) {
      setErrorMsg(extractErrorMessage(err));
    }
  };

  const handleRerunQuality = async (imageId: string) => {
    setErrorMsg(null);
    try {
      await api.post(`/images/${imageId}/quality-check`);
      await refetch();
    } catch (err) {
      setErrorMsg(extractErrorMessage(err));
    }
  };

  if (isLoading && !images.length) return <LoadingSkeleton rows={6} />;

  return (
    <Box>
      <PatientContextHeader
        patientId={visitDetail?.patient_id}
        patientCode={visitDetail?.patient_code}
        fractureSide={visitDetail?.fracture_side}
        surgeryDate={visitDetail?.surgery_date}
        studyStatus={visitDetail?.study_status}
        visitId={activeVisitId}
        visitType={visitDetail?.visit_type}
      />
      <ResearchDisclaimerBanner compact />

      <PageHeader
        title="Image Acquisition, Validation & Quality Assessment"
        subtitle="Upload or replace the 4 standardized visit images and complete manual quality acceptance before AI landmark analysis"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 260, bgcolor: '#FFF' }}>
              <InputLabel>Select Study Visit</InputLabel>
              <Select
                label="Select Study Visit"
                value={activeVisitId}
                onChange={(e) => {
                  setSelectedVisitId(e.target.value);
                  navigate(`/visits/${e.target.value}/images`);
                }}
              >
                {allVisits.map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {v.patient_code} — {v.visit_type} ({v.image_count}/4 views)
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="outlined"
              color="secondary"
              startIcon={<AutoFixHighIcon />}
              disabled={busyView === 'ALL'}
              onClick={handleGenerateSyntheticSet}
            >
              {busyView === 'ALL' ? 'Generating...' : 'Load 4 Synthetic Demo Images'}
            </Button>

            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              disabled={images.length === 0}
              onClick={() => navigate(`/ai-analysis/${activeVisitId}`)}
            >
              Proceed to AI Analysis Workspace
            </Button>
          </>
        }
      />

      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}
      {successMsg && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {successMsg}
        </Alert>
      )}

      <Grid container spacing={2.5}>
        {FOUR_VIEWS.map((panel) => {
          const rec = byType.get(panel.type);
          const q = rec?.quality_result;
          const isBusy = busyView === panel.type;

          return (
            <Grid key={panel.type} size={{ xs: 12, md: 6 }}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 1 }}>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                        {panel.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {panel.protocolHint}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={0.8}>
                      {rec ? (
                        <>
                          <StatusBadge status={q?.status || 'Pending'} />
                          <StatusBadge status={rec.acceptance_status} />
                        </>
                      ) : (
                        <Chip size="small" label="Not Uploaded" />
                      )}
                    </Stack>
                  </Stack>

                  {isBusy && <LinearProgress sx={{ my: 1 }} />}

                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
                    style={{ display: 'none' }}
                    ref={(el) => {
                      fileInputRefs.current[panel.type] = el;
                    }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleFileUpload(panel.type, f);
                      e.target.value = '';
                    }}
                  />

                  {!rec ? (
                    <Box
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        const f = e.dataTransfer.files?.[0];
                        if (f) handleFileUpload(panel.type, f);
                      }}
                      onClick={() => fileInputRefs.current[panel.type]?.click()}
                      sx={{
                        mt: 1.5,
                        p: 4,
                        border: '2px dashed #94A3B8',
                        borderRadius: 2,
                        textAlign: 'center',
                        cursor: 'pointer',
                        backgroundColor: '#F8FAFC',
                        '&:hover': { backgroundColor: '#F1F5F9', borderColor: '#087E8B' },
                      }}
                    >
                      <CloudUploadOutlinedIcon sx={{ fontSize: 38, color: '#087E8B', mb: 1 }} />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Drag & drop {panel.type} image here, or click to browse
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Allowed: JPEG, PNG, TIFF, BMP | Min 400×400 px | Max 50 MB
                      </Typography>
                    </Box>
                  ) : (
                    <Box sx={{ mt: 1.5 }}>
                      <Grid container spacing={2}>
                        <Grid size={{ xs: 12, sm: 5 }}>
                          <Box
                            sx={{
                              borderRadius: 2,
                              overflow: 'hidden',
                              border: '1px solid #CBD5E1',
                              bgcolor: '#0F172A',
                              height: 210,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            <img
                              src={withAuthTokenUrl(rec.file_url)}
                              alt={rec.image_type}
                              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                            />
                          </Box>
                          <Stack direction="row" spacing={0.8} sx={{ mt: 1 }} flexWrap="wrap">
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => fileInputRefs.current[panel.type]?.click()}
                            >
                              Replace
                            </Button>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<RefreshIcon fontSize="small" />}
                              onClick={() => handleRerunQuality(rec.id)}
                            >
                              Re-check
                            </Button>
                            <Button
                              size="small"
                              color="error"
                              startIcon={<DeleteOutlineIcon fontSize="small" />}
                              onClick={() => handleDeleteImage(rec.id)}
                            >
                              Remove
                            </Button>
                          </Stack>
                        </Grid>

                        <Grid size={{ xs: 12, sm: 7 }}>
                          <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
                            FILE & DEVICE METADATA
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                            File: {rec.original_filename} ({rec.width}×{rec.height} px,{' '}
                            {Math.round((rec.file_size || 0) / 1024)} KB)
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                            Captured: {rec.capture_date ? new Date(rec.capture_date).toLocaleDateString() : 'Recorded'}
                            {rec.is_synthetic ? ' • SYNTHETIC DEMO IMAGE' : ''}
                          </Typography>

                          <Divider sx={{ my: 1 }} />
                          <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', mb: 0.5 }}>
                            HEURISTIC AI QUALITY SCREEN ({q?.model_name || 'heuristic-v1'})
                          </Typography>
                          {q && (
                            <Stack direction="row" spacing={0.6} flexWrap="wrap" sx={{ mb: 1 }}>
                              <Chip size="small" label={`Resolution: ${q.resolution_check?.status || 'Pass'}`} />
                              <Chip size="small" label={`Blur: ${q.blur_check?.status || 'Pass'}`} />
                              <Chip size="small" label={`Lighting: ${q.lighting_check?.status || 'Pass'}`} />
                              <Chip size="small" label={`Framing: ${q.framing_check?.status || 'Pass'}`} />
                              {panel.type !== 'OPG' && (
                                <Chip size="small" label={`Face/Pose: ${q.orientation_check?.status || 'Pass'}`} />
                              )}
                            </Stack>
                          )}

                          {q?.issues && q.issues.length > 0 && (
                            <Alert severity="warning" sx={{ py: 0.2, mb: 1, fontSize: '0.74rem' }}>
                              {q.issues.join(' • ')}
                            </Alert>
                          )}
                          {q?.suggestions && q.suggestions.length > 0 && (
                            <Typography variant="caption" color="warning.main" sx={{ display: 'block', mb: 1 }}>
                              Recapture advice: {q.suggestions.join(' ')}
                            </Typography>
                          )}

                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                            <i>Note:</i> Screening status does not establish clinical adequacy. Manual acceptance or rejection is required:
                          </Typography>

                          <Stack direction="row" spacing={1}>
                            <Button
                              size="small"
                              variant={rec.acceptance_status === 'Accepted' ? 'contained' : 'outlined'}
                              color="success"
                              startIcon={<CheckCircleOutlineIcon fontSize="small" />}
                              onClick={() => handleManualDecision(rec.id, 'Accepted')}
                            >
                              Accept Image
                            </Button>
                            <Button
                              size="small"
                              variant={rec.acceptance_status === 'Rejected' ? 'contained' : 'outlined'}
                              color="error"
                              startIcon={<CancelOutlinedIcon fontSize="small" />}
                              onClick={() => handleManualDecision(rec.id, 'Rejected')}
                            >
                              Reject (Recapture)
                            </Button>
                          </Stack>
                        </Grid>
                      </Grid>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
};
