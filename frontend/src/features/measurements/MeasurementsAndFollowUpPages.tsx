import React, { useEffect, useMemo, useState } from 'react';
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
  MenuItem,
  Select,
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
import CalculateIcon from '@mui/icons-material/Calculate';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DownloadIcon from '@mui/icons-material/Download';
import ScaleIcon from '@mui/icons-material/Scale';
import TimelineIcon from '@mui/icons-material/Timeline';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { api, extractErrorMessage, withAuthTokenUrl } from '@/services/api';
import {
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingSkeleton,
  PageHeader,
  PatientContextHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { MeasurementItem, PatientSummary, VisitSummary } from '@/types';
import { useAuthStore } from '@/store/authStore';

// ============================================================================
// PAGE 12: Measurement Results and Asymmetry Calculation Screen
// ============================================================================
export const MeasurementResultsPage: React.FC = () => {
  const { visitId } = useParams<{ visitId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeVisitId = useAuthStore((s) => s.activeContext.visitId);
  const resolvedVisitId = visitId || activeVisitId || '';

  const [selectedVisitId, setSelectedVisitId] = useState<string>(resolvedVisitId);
  const [methodTab, setMethodTab] = useState<'ALL' | 'AIPredicted' | 'ExaminerReviewed' | 'Validated'>('ALL');
  const [selectedMeas, setSelectedMeas] = useState<MeasurementItem | null>(null);
  const [reviewComment, setReviewComment] = useState<string>(
    'Verified landmark placement, view-specific physical calibration, and bilateral calculation'
  );
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const visitsQuery = useQuery({
    queryKey: ['visits-for-measurements'],
    queryFn: async () => {
      const res = await api.get('/visits');
      return res.data.data as VisitSummary[];
    },
  });

  useEffect(() => {
    if (!selectedVisitId && visitsQuery.data && visitsQuery.data.length > 0) {
      setSelectedVisitId(visitsQuery.data[0].id);
    }
  }, [selectedVisitId, visitsQuery.data]);

  const measQuery = useQuery({
    queryKey: ['visit-measurements', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/measurements/visits/${selectedVisitId}`);
      return res.data.data as {
        visit_id: string;
        summary: {
          total: number;
          approved: number;
          reviewed: number;
          predicted: number;
          unscaled: number;
          missing: number;
          mean_asymmetry_index: number | null;
        };
        measurements: MeasurementItem[];
      };
    },
  });

  const recalcMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/measurements/visits/${selectedVisitId}/recalculate`);
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: `Recalculated ${res.recalculated_count} bilateral & angular measurements using active calibrations and landmarks.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-measurements', selectedVisitId] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const approveOneMut = useMutation({
    mutationFn: async (payload: { id: string; status: 'Approved' | 'Rejected'; comments: string }) => {
      const res = await api.post(`/measurements/${payload.id}/approve`, {
        status: payload.status,
        comments: payload.comments,
      });
      return res.data.data;
    },
    onSuccess: (updated) => {
      setSelectedMeas(null);
      setFeedback({
        type: 'success',
        text: `Measurement ${updated.code} marked as ${updated.status}.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-measurements', selectedVisitId] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const batchApproveMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/measurements/visits/${selectedVisitId}/approve-batch`, {
        status: 'Approved',
        comments: 'Batch validated and approved by clinical examiner',
      });
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: `Batch approved ${res.updated_count} valid measurements. Visit status: ${res.visit_status}.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-measurements', selectedVisitId] });
      queryClient.invalidateQueries({ queryKey: ['visits-for-measurements'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const filteredMeasurements = useMemo(() => {
    const all = measQuery.data?.measurements || [];
    if (methodTab === 'ALL') return all;
    return all.filter((m) => m.method === methodTab);
  }, [measQuery.data, methodTab]);

  const activeVisitObj = (visitsQuery.data || []).find((v) => v.id === selectedVisitId);
  const summary = measQuery.data?.summary;

  return (
    <Box>
      <ResearchDisclaimerBanner compact />
      <PatientContextHeader
        patientId={activeVisitObj?.patient_id}
        patientCode={activeVisitObj?.patient_code}
        fractureSide={activeVisitObj?.fracture_side}
        surgeryDate={activeVisitObj?.surgery_date}
        studyStatus={activeVisitObj?.study_status}
        visitId={selectedVisitId}
        visitType={activeVisitObj?.visit_type}
      />

      <PageHeader
        title="Quantitative Facial & Mandibular Asymmetry Measurements"
        subtitle="Bilateral linear, angular, OPG radiographic, and 3D geodesic measurements with explicit AI-Predicted vs Examiner-Reviewed vs Validated separation"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 250, backgroundColor: '#FFF' }}>
              <InputLabel>Study Visit</InputLabel>
              <Select
                label="Study Visit"
                value={selectedVisitId}
                onChange={(e) => setSelectedVisitId(e.target.value)}
              >
                {(visitsQuery.data || []).map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {v.patient_code} — {v.label || v.visit_type}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="outlined"
              startIcon={<ScaleIcon />}
              onClick={() => navigate(`/calibration/${selectedVisitId}`)}
            >
              Calibration
            </Button>
            <Button
              variant="outlined"
              startIcon={<CalculateIcon />}
              disabled={!selectedVisitId || recalcMut.isPending}
              onClick={() => recalcMut.mutate()}
            >
              Recalculate
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<CheckCircleIcon />}
              disabled={!selectedVisitId || batchApproveMut.isPending}
              onClick={() => batchApproveMut.mutate()}
            >
              Approve All Valid Measurements
            </Button>
            {selectedVisitId && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  component="a"
                  href={withAuthTokenUrl(`/api/v1/measurements/visits/${selectedVisitId}/export?format=csv`)}
                  target="_blank"
                >
                  CSV
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  component="a"
                  href={withAuthTokenUrl(`/api/v1/measurements/visits/${selectedVisitId}/export?format=xlsx`)}
                  target="_blank"
                >
                  Excel
                </Button>
              </>
            )}
          </>
        }
      />

      {feedback && (
        <Alert severity={feedback.type} sx={{ mb: 2 }} onClose={() => setFeedback(null)}>
          {feedback.text}
        </Alert>
      )}

      {measQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : measQuery.isError ? (
        <ErrorState message={extractErrorMessage(measQuery.error)} onRetry={() => measQuery.refetch()} />
      ) : (
        <Stack spacing={2.5}>
          {/* KPI Summary Strip */}
          {summary && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard label="Total Metrics" value={summary.total} subtitle="Protocol-defined" />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="AI-Predicted"
                  value={summary.predicted}
                  subtitle="Awaiting examiner review"
                  accent="#9333EA"
                />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Examiner-Reviewed"
                  value={summary.reviewed}
                  subtitle="Adjusted / inspected"
                  accent="#0284C7"
                />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Validated / Approved"
                  value={summary.approved}
                  subtitle="Signed off for research"
                  accent="#16A34A"
                />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Unscaled / Missing"
                  value={`${summary.unscaled} / ${summary.missing}`}
                  subtitle="Never fabricated"
                  accent="#D97706"
                />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Mean Asymmetry Index"
                  value={
                    summary.mean_asymmetry_index != null
                      ? `${summary.mean_asymmetry_index.toFixed(2)} %`
                      : 'N/A'
                  }
                  subtitle="|R - L| / (R + L) × 100"
                  accent="#123B50"
                />
              </Grid>
            </Grid>
          )}

          {/* Filter Tabs Separating AI-Predicted, Examiner-Reviewed, and Validated */}
          <Card>
            <Box sx={{ borderBottom: '1px solid #E2E8F0', px: 2 }}>
              <Tabs
                value={methodTab}
                onChange={(_, v) => setMethodTab(v)}
                textColor="primary"
                indicatorColor="secondary"
              >
                <Tab value="ALL" label={`All Measurements (${measQuery.data?.measurements.length || 0})`} />
                <Tab value="AIPredicted" label={`AI-Predicted (${summary?.predicted || 0})`} />
                <Tab value="ExaminerReviewed" label={`Examiner-Reviewed (${summary?.reviewed || 0})`} />
                <Tab value="Validated" label={`Validated / Approved (${summary?.approved || 0})`} />
              </Tabs>
            </Box>

            <CardContent sx={{ p: 0 }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Code & Measurement Name</TableCell>
                      <TableCell>Category & View</TableCell>
                      <TableCell align="right">Right Value</TableCell>
                      <TableCell align="right">Left Value</TableCell>
                      <TableCell align="right">|R - L| Diff</TableCell>
                      <TableCell align="right">Asymmetry Index (%)</TableCell>
                      <TableCell>Unit & Scale</TableCell>
                      <TableCell>Method Tier</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filteredMeasurements.map((m) => (
                      <TableRow key={m.id} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: '#123B50' }}>
                            {m.code} — {m.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {m.formula}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{m.measurement_type}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            View: {m.source_image_type}
                          </Typography>
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                          {m.right_value != null ? m.right_value.toFixed(2) : 'Missing'}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                          {m.left_value != null ? m.left_value.toFixed(2) : '—'}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                          {m.absolute_difference != null ? m.absolute_difference.toFixed(2) : '—'}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 700, color: '#087E8B' }}>
                          {m.asymmetry_index != null ? `${m.asymmetry_index.toFixed(2)} %` : '—'}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={m.unit}
                            color={m.is_unscaled ? 'warning' : 'default'}
                            sx={{ fontSize: '0.72rem', fontWeight: 600 }}
                          />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={m.method} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={m.status} />
                        </TableCell>
                        <TableCell align="right">
                          <Button size="small" variant="outlined" onClick={() => setSelectedMeas(m)}>
                            Inspect / Sign-Off
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Stack>
      )}

      {/* Measurement Provenance & Examiner Sign-Off Modal */}
      <Dialog open={Boolean(selectedMeas)} onClose={() => setSelectedMeas(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          {selectedMeas?.code} — {selectedMeas?.name} (v{selectedMeas?.version})
        </DialogTitle>
        <DialogContent dividers>
          {selectedMeas && (
            <Stack spacing={2}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Typography variant="caption" color="text.secondary">
                    FORMULA & METHODOLOGY
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {selectedMeas.formula}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    {selectedMeas.description}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Typography variant="caption" color="text.secondary">
                    CALIBRATION & PROVENANCE REFERENCE
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {selectedMeas.calibration_reference}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    Model: {selectedMeas.model_name} ({selectedMeas.model_version}) • Method Tier:{' '}
                    <strong>{selectedMeas.method}</strong>
                  </Typography>
                </Grid>
              </Grid>

              <Divider />

              <Grid container spacing={2}>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    RIGHT VALUE
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {selectedMeas.right_value != null
                      ? `${selectedMeas.right_value.toFixed(2)} ${selectedMeas.unit}`
                      : 'Missing'}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    LEFT VALUE
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {selectedMeas.left_value != null
                      ? `${selectedMeas.left_value.toFixed(2)} ${selectedMeas.unit}`
                      : 'N/A'}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    ABSOLUTE DIFF |R - L|
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {selectedMeas.absolute_difference != null
                      ? `${selectedMeas.absolute_difference.toFixed(2)} ${selectedMeas.unit}`
                      : 'N/A'}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    ASYMMETRY INDEX (%)
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: '#087E8B' }}>
                    {selectedMeas.asymmetry_index != null
                      ? `${selectedMeas.asymmetry_index.toFixed(2)} %`
                      : 'N/A'}
                  </Typography>
                </Grid>
              </Grid>

              {selectedMeas.warnings?.map((w, i) => (
                <Alert key={i} severity="warning">
                  {w}
                </Alert>
              ))}

              <Box>
                <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', mb: 0.5 }}>
                  REFERENCED LANDMARKS & COORDINATES
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 1.5,
                    borderRadius: 1,
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #E2E8F0',
                    fontSize: '0.75rem',
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(selectedMeas.landmark_refs, null, 2)}
                </Box>
              </Box>

              <TextField
                label="Examiner Sign-Off / Review Notes"
                size="small"
                fullWidth
                multiline
                rows={2}
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedMeas(null)}>Close</Button>
          {selectedMeas && (
            <>
              <Button
                variant="outlined"
                color="error"
                disabled={approveOneMut.isPending}
                onClick={() =>
                  approveOneMut.mutate({
                    id: selectedMeas.id,
                    status: 'Rejected',
                    comments: reviewComment,
                  })
                }
              >
                Reject Measurement
              </Button>
              <Button
                variant="contained"
                color="secondary"
                disabled={approveOneMut.isPending || selectedMeas.status === 'MissingData'}
                onClick={() =>
                  approveOneMut.mutate({
                    id: selectedMeas.id,
                    status: 'Approved',
                    comments: reviewComment,
                  })
                }
              >
                Approve & Validate
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 13: Longitudinal Follow-Up Comparison Workspace
// ============================================================================
export const FollowUpComparisonPage: React.FC = () => {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const activePatientId = useAuthStore((s) => s.activeContext.patientId);
  const resolvedPatientId = patientId || activePatientId || '';

  const [selectedPatientId, setSelectedPatientId] = useState<string>(resolvedPatientId);
  const [selectedMetricCode, setSelectedMetricCode] = useState<string>('BIGONIAL_BREADTH');
  const [selectedImageView, setSelectedImageView] = useState<'Frontal' | 'RightLateral' | 'LeftLateral' | 'OPG'>(
    'Frontal'
  );

  const patientsQuery = useQuery({
    queryKey: ['patients-for-followup'],
    queryFn: async () => {
      const res = await api.get('/patients?page=1&page_size=50');
      const d = res.data.data;
      return (Array.isArray(d) ? d : d?.items || []) as PatientSummary[];
    },
  });

  useEffect(() => {
    if (!selectedPatientId && patientsQuery.data && patientsQuery.data.length > 0) {
      setSelectedPatientId(patientsQuery.data[0].id);
    }
  }, [selectedPatientId, patientsQuery.data]);

  const followUpQuery = useQuery({
    queryKey: ['patient-follow-up', selectedPatientId],
    enabled: Boolean(selectedPatientId),
    queryFn: async () => {
      const res = await api.get(`/measurements/patients/${selectedPatientId}/follow-up`);
      return res.data.data as {
        patient_id: string;
        patient_code: string;
        fracture_side: string;
        fracture_type: string;
        surgery_date: string;
        fixation_type: string;
        is_synthetic: boolean;
        visits: Array<{
          visit_id: string;
          visit_type: string;
          label: string;
          planned_date: string;
          actual_date: string | null;
          status: string;
          images: Record<string, string>;
          has_3d_mesh: boolean;
          mesh_status: string | null;
          clinical_assessment: Record<string, any> | null;
          measurements: Record<string, any>;
        }>;
        series_by_measurement: Record<
          string,
          {
            code: string;
            name: string;
            unit: string;
            measurement_type: string;
            points: Array<{
              visit_type: string;
              label: string;
              visit_status: string;
              available: boolean;
              right_value: number | null;
              left_value: number | null;
              absolute_difference: number | null;
              asymmetry_index: number | null;
              status: string;
              method: string | null;
            }>;
          }
        >;
      };
    },
  });

  const data = followUpQuery.data;
  const activeSeries = data?.series_by_measurement?.[selectedMetricCode];

  return (
    <Box>
      <ResearchDisclaimerBanner compact />
      {data && (
        <PatientContextHeader
          patientId={data.patient_id}
          patientCode={data.patient_code}
          fractureSide={data.fracture_side}
          surgeryDate={data.surgery_date}
          isSynthetic={data.is_synthetic}
        />
      )}

      <PageHeader
        title="Longitudinal Follow-Up Comparison Workspace"
        subtitle="Compare Pre-operative, 1-week, 6-week, 3-month, and 6-month trajectory across measurements, standardized views, 3D meshes, and clinical healing"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 260, backgroundColor: '#FFF' }}>
              <InputLabel>Select Patient</InputLabel>
              <Select
                label="Select Patient"
                value={selectedPatientId}
                onChange={(e) => setSelectedPatientId(e.target.value)}
              >
                {(patientsQuery.data || []).map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.patient_code} ({p.fracture_side} {p.fracture_type})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {data && (
              <FormControl size="small" sx={{ minWidth: 280, backgroundColor: '#FFF' }}>
                <InputLabel>Measurement Parameter</InputLabel>
                <Select
                  label="Measurement Parameter"
                  value={selectedMetricCode}
                  onChange={(e) => setSelectedMetricCode(e.target.value)}
                >
                  {Object.values(data.series_by_measurement).map((s) => (
                    <MenuItem key={s.code} value={s.code}>
                      {s.code} — {s.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </>
        }
      />

      {followUpQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : followUpQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(followUpQuery.error)}
          onRetry={() => followUpQuery.refetch()}
        />
      ) : !data ? (
        <EmptyState title="Select a patient to view longitudinal follow-up progression" />
      ) : (
        <Stack spacing={2.5}>
          <Alert severity="info">
            <strong>Longitudinal Data Integrity Policy:</strong> Missing or pending follow-up visits are explicitly displayed as <strong>Missing / Pending</strong> and are never interpolated or fabricated on trend charts.
          </Alert>

          {/* Trajectory Charts */}
          {activeSeries && (
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, lg: 6 }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                      Asymmetry Index (%) & |R - L| Trajectory — {activeSeries.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                      Progressive reduction in Asymmetry Index (%) across post-fixation follow-up stages
                    </Typography>
                    <Box sx={{ width: '100%', height: 290 }}>
                      <ResponsiveContainer>
                        <LineChart data={activeSeries.points}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <RechartsTooltip />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="asymmetry_index"
                            name="Asymmetry Index (%)"
                            stroke="#087E8B"
                            strokeWidth={3}
                            connectNulls={false}
                            dot={{ r: 5 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="absolute_difference"
                            name={`|R - L| (${activeSeries.unit})`}
                            stroke="#F59E0B"
                            strokeWidth={2.5}
                            connectNulls={false}
                            dot={{ r: 4 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, lg: 6 }}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                      Right vs Left Bilateral Comparison ({activeSeries.unit})
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                      Fracture side: <strong>{data.fracture_side}</strong> • Fixation: {data.fixation_type}
                    </Typography>
                    <Box sx={{ width: '100%', height: 290 }}>
                      <ResponsiveContainer>
                        <BarChart data={activeSeries.points}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <RechartsTooltip />
                          <Legend />
                          <Bar dataKey="right_value" name="Right Side" fill="#123B50" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="left_value" name="Left Side" fill="#087E8B" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}

          {/* Side-by-Side Longitudinal Image Comparison Strip */}
          <Card>
            <CardContent>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                flexWrap="wrap"
                spacing={1}
                sx={{ mb: 2 }}
              >
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  Side-by-Side Longitudinal Image & 3D Mesh Comparison Across 5 Study Visits
                </Typography>
                <Stack direction="row" spacing={1}>
                  {(['Frontal', 'RightLateral', 'LeftLateral', 'OPG'] as const).map((vt) => (
                    <Button
                      key={vt}
                      size="small"
                      variant={selectedImageView === vt ? 'contained' : 'outlined'}
                      onClick={() => setSelectedImageView(vt)}
                    >
                      {vt}
                    </Button>
                  ))}
                </Stack>
              </Stack>

              <Grid container spacing={2}>
                {data.visits.map((v) => {
                  const imgUrl = v.images?.[selectedImageView];
                  return (
                    <Grid key={v.visit_id} size={{ xs: 12, sm: 6, md: 2.4 }}>
                      <Box
                        sx={{
                          p: 1.2,
                          borderRadius: 2,
                          border: '1px solid #E2E8F0',
                          backgroundColor: '#F8FAFC',
                          height: '100%',
                          display: 'flex',
                          flexDirection: 'column',
                        }}
                      >
                        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.8 }}>
                          <Typography variant="caption" sx={{ fontWeight: 700, color: '#123B50' }}>
                            {v.label}
                          </Typography>
                          <StatusBadge status={v.status} />
                        </Stack>
                        <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
                          Date: {v.actual_date || v.planned_date || 'Scheduled'}
                        </Typography>

                        {imgUrl ? (
                          <Box
                            component="img"
                            src={withAuthTokenUrl(imgUrl)}
                            alt={`${v.label} ${selectedImageView}`}
                            sx={{
                              width: '100%',
                              height: 170,
                              objectFit: 'contain',
                              backgroundColor: '#0F172A',
                              borderRadius: 1.5,
                              mb: 1,
                            }}
                          />
                        ) : (
                          <Box
                            sx={{
                              height: 170,
                              borderRadius: 1.5,
                              backgroundColor: '#F1F5F9',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              mb: 1,
                              color: '#64748B',
                              fontSize: '0.78rem',
                              textAlign: 'center',
                              p: 1,
                            }}
                          >
                            Missing / Pending Visit Image
                          </Box>
                        )}

                        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 'auto' }}>
                          <Chip
                            size="small"
                            label={v.has_3d_mesh ? `3D: ${v.mesh_status}` : 'No 3D Mesh'}
                            sx={{ fontSize: '0.68rem' }}
                          />
                          <Button
                            size="small"
                            onClick={() => navigate(`/measurements/${v.visit_id}`)}
                          >
                            Open
                          </Button>
                        </Stack>
                      </Box>
                    </Grid>
                  );
                })}
              </Grid>
            </CardContent>
          </Card>

          {/* Longitudinal Quantitative & Clinical Table */}
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                Visit-by-Visit Quantitative & Clinical Healing Comparison Table ({activeSeries?.name})
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Follow-Up Stage</TableCell>
                      <TableCell>Visit Status</TableCell>
                      <TableCell align="right">Right Value</TableCell>
                      <TableCell align="right">Left Value</TableCell>
                      <TableCell align="right">|R - L| Diff</TableCell>
                      <TableCell align="right">Asymmetry Index (%)</TableCell>
                      <TableCell>Validation Method</TableCell>
                      <TableCell>Swelling / Occlusion / Trismus (mm)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.visits.map((v, idx) => {
                      const pt = activeSeries?.points[idx];
                      const ca = v.clinical_assessment;
                      return (
                        <TableRow key={v.visit_id} hover>
                          <TableCell sx={{ fontWeight: 700 }}>{v.label}</TableCell>
                          <TableCell>
                            <StatusBadge status={v.status} />
                          </TableCell>
                          <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                            {pt?.right_value != null ? pt.right_value.toFixed(2) : 'Missing'}
                          </TableCell>
                          <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                            {pt?.left_value != null ? pt.left_value.toFixed(2) : 'Missing'}
                          </TableCell>
                          <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                            {pt?.absolute_difference != null ? pt.absolute_difference.toFixed(2) : 'Missing'}
                          </TableCell>
                          <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 700, color: '#087E8B' }}>
                            {pt?.asymmetry_index != null ? `${pt.asymmetry_index.toFixed(2)} %` : 'Missing'}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={pt?.method || 'MissingData'} />
                          </TableCell>
                          <TableCell>
                            {ca ? (
                              <Typography variant="caption">
                                Swelling: <strong>{ca.swelling_grade}</strong> • Occlusion:{' '}
                                <strong>{ca.occlusion_status}</strong> • Mouth Opening:{' '}
                                <strong>{ca.interincisal_opening_mm} mm</strong>
                              </Typography>
                            ) : (
                              <Typography variant="caption" color="text.secondary">
                                Not recorded yet
                              </Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Stack>
      )}
    </Box>
  );
};
