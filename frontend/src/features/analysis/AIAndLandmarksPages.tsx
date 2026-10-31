import React, { useEffect, useMemo, useRef, useState } from 'react';
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
  FormControlLabel,
  Grid2 as Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ReplayIcon from '@mui/icons-material/Replay';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import FitScreenIcon from '@mui/icons-material/FitScreen';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import AddLocationAltIcon from '@mui/icons-material/AddLocationAlt';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import StraightenIcon from '@mui/icons-material/Straighten';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
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
import { AIStageJob, LandmarkRecord, VisitImageRecord, VisitSummary } from '@/types';
import { useAuthStore } from '@/store/authStore';

// ============================================================================
// PAGE 8: AI Analysis Workspace
// ============================================================================
export const AIAnalysisWorkspacePage: React.FC = () => {
  const { visitId } = useParams<{ visitId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeVisitId = useAuthStore((s) => s.activeContext.visitId);
  const setActiveContext = useAuthStore((s) => s.setActiveContext);
  const resolvedVisitId = visitId || activeVisitId || '';

  const [selectedVisitId, setSelectedVisitId] = useState<string>(resolvedVisitId);
  const [liveEvents, setLiveEvents] = useState<Array<Record<string, any>>>([]);
  const [actionMsg, setActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [selectedStage, setSelectedStage] = useState<AIStageJob | null>(null);

  const visitsListQuery = useQuery({
    queryKey: ['visits-all-for-ai'],
    queryFn: async () => {
      const res = await api.get('/visits');
      return res.data.data as VisitSummary[];
    },
  });

  useEffect(() => {
    if (!selectedVisitId && visitsListQuery.data && visitsListQuery.data.length > 0) {
      const first = visitsListQuery.data[0];
      setSelectedVisitId(first.id);
      setActiveContext({
        patientId: first.patient_id,
        patientCode: first.patient_code,
        fractureSide: first.fracture_side,
        surgeryDate: first.surgery_date,
        studyStatus: first.study_status,
        visitId: first.id,
        visitType: first.visit_type,
      });
    }
  }, [selectedVisitId, visitsListQuery.data, setActiveContext]);

  const pipelineQuery = useQuery({
    queryKey: ['ai-pipeline-visit', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/ai/visits/${selectedVisitId}/pipeline`);
      return res.data.data as {
        visit_id: string;
        overall_status: string;
        stages: AIStageJob[];
      };
    },
  });

  // Real-time Server-Sent Events (SSE) subscription for stage updates
  useEffect(() => {
    if (!selectedVisitId) return;
    const streamUrl = withAuthTokenUrl(`/api/v1/ai/visits/${selectedVisitId}/stream`);
    let es: EventSource | null = null;
    try {
      es = new EventSource(streamUrl);
      es.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.event !== 'heartbeat') {
            setLiveEvents((prev) => [payload, ...prev].slice(0, 20));
            queryClient.invalidateQueries({ queryKey: ['ai-pipeline-visit', selectedVisitId] });
          }
        } catch {
          // ignore parse error
        }
      };
    } catch {
      // ignore if EventSource is unavailable in test environment
    }
    return () => {
      if (es) es.close();
    };
  }, [selectedVisitId, queryClient]);

  const runPipelineMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/ai/visits/${selectedVisitId}/run`, {});
      return res.data.data;
    },
    onSuccess: () => {
      setActionMsg({
        type: 'success',
        text: '11-stage AI analysis pipeline executed. Visit status moved to ReviewRequired pending examiner landmark & measurement sign-off.',
      });
      queryClient.invalidateQueries({ queryKey: ['ai-pipeline-visit', selectedVisitId] });
      queryClient.invalidateQueries({ queryKey: ['visit-detail', selectedVisitId] });
    },
    onError: (err) => setActionMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const retryStageMut = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await api.post(`/ai/jobs/${jobId}/retry`);
      return res.data.data;
    },
    onSuccess: () => {
      setActionMsg({ type: 'success', text: 'Pipeline stage retried successfully.' });
      queryClient.invalidateQueries({ queryKey: ['ai-pipeline-visit', selectedVisitId] });
    },
    onError: (err) => setActionMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const activeVisitObj = useMemo(
    () => (visitsListQuery.data || []).find((v) => v.id === selectedVisitId),
    [visitsListQuery.data, selectedVisitId]
  );

  const stages = pipelineQuery.data?.stages || [];
  const completedCount = stages.filter((s) => s.status === 'Completed').length;
  const progressPct = stages.length > 0 ? Math.round((completedCount / stages.length) * 100) : 0;

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
        title="AI Analysis Pipeline Workspace"
        subtitle="11-stage multi-modal facial & OPG processing pipeline with task-specific provider adapters and real-time execution telemetry"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 260, backgroundColor: '#FFF' }}>
              <InputLabel>Active Study Visit</InputLabel>
              <Select
                label="Active Study Visit"
                value={selectedVisitId}
                onChange={(e) => {
                  const vid = e.target.value;
                  setSelectedVisitId(vid);
                  const found = (visitsListQuery.data || []).find((v) => v.id === vid);
                  if (found) {
                    setActiveContext({
                      patientId: found.patient_id,
                      patientCode: found.patient_code,
                      fractureSide: found.fracture_side,
                      surgeryDate: found.surgery_date,
                      studyStatus: found.study_status,
                      visitId: found.id,
                      visitType: found.visit_type,
                    });
                  }
                }}
              >
                {(visitsListQuery.data || []).map((v) => (
                  <MenuItem key={v.id} value={v.id}>
                    {v.patient_code} — {v.label || v.visit_type} ({v.status})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="contained"
              color="secondary"
              startIcon={<PlayArrowIcon />}
              disabled={!selectedVisitId || runPipelineMut.isPending}
              onClick={() => runPipelineMut.mutate()}
            >
              {runPipelineMut.isPending ? 'Running 11-Stage Pipeline...' : 'Run Full AI Pipeline'}
            </Button>

            {selectedVisitId && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<AutoAwesomeIcon />}
                  onClick={() => navigate(`/landmarks/${selectedVisitId}`)}
                >
                  Review Landmarks
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<ViewInArIcon />}
                  onClick={() => navigate(`/reconstruction/${selectedVisitId}`)}
                >
                  3D Mesh
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<StraightenIcon />}
                  onClick={() => navigate(`/measurements/${selectedVisitId}`)}
                >
                  Measurements
                </Button>
              </>
            )}
          </>
        }
      />

      {actionMsg && (
        <Alert severity={actionMsg.type} sx={{ mb: 2 }} onClose={() => setActionMsg(null)}>
          {actionMsg.text}
        </Alert>
      )}

      {pipelineQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : pipelineQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(pipelineQuery.error)}
          onRetry={() => pipelineQuery.refetch()}
        />
      ) : !selectedVisitId ? (
        <EmptyState title="Select a visit to inspect or launch the AI pipeline" />
      ) : (
        <Stack spacing={2.5}>
          {/* Summary Progress Bar */}
          <Card>
            <CardContent>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                justifyContent="space-between"
                alignItems={{ xs: 'flex-start', sm: 'center' }}
                spacing={1.5}
                sx={{ mb: 1.5 }}
              >
                <Box>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                      Pipeline Status:
                    </Typography>
                    <StatusBadge status={pipelineQuery.data?.overall_status || 'Pending'} size="medium" />
                    <Typography variant="body2" color="text.secondary">
                      ({completedCount} / {stages.length} stages completed)
                    </Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    Note: Completing AI execution never marks a study visit as Completed automatically — examiner landmark review and measurement sign-off are mandatory.
                  </Typography>
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 700, color: '#087E8B' }}>
                  {progressPct}%
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={progressPct}
                color="secondary"
                sx={{ height: 10, borderRadius: 5 }}
              />
            </CardContent>
          </Card>

          {/* 11 Pipeline Stage Cards */}
          <Grid container spacing={2}>
            {stages.map((stage) => (
              <Grid key={stage.stage_order} size={{ xs: 12, md: 6, lg: 4 }}>
                <Card
                  sx={{
                    height: '100%',
                    borderLeft: `4px solid ${
                      stage.status === 'Completed'
                        ? '#16A34A'
                        : stage.status === 'Failed'
                        ? '#DC2626'
                        : stage.status === 'Processing'
                        ? '#2563EB'
                        : '#94A3B8'
                    }`,
                  }}
                >
                  <CardContent sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 1 }}>
                      <Box>
                        <Typography variant="caption" sx={{ color: '#64748B', fontWeight: 700 }}>
                          STAGE {stage.stage_order} • {stage.task_type}
                        </Typography>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#123B50' }}>
                          {stage.stage_label}
                        </Typography>
                      </Box>
                      <StatusBadge status={stage.status} />
                    </Stack>

                    <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 1.5 }}>
                      <Chip
                        size="small"
                        label={`Provider: ${stage.provider}`}
                        sx={{ fontSize: '0.72rem', fontWeight: 600 }}
                      />
                      {stage.model_name && (
                        <Chip
                          size="small"
                          variant="outlined"
                          label={`${stage.model_name} (${stage.model_version || 'v1'})`}
                          sx={{ fontSize: '0.72rem' }}
                        />
                      )}
                      {stage.is_demo && (
                        <Chip
                          size="small"
                          color="warning"
                          label="SYNTHETIC DEMO ADAPTER"
                          sx={{ fontSize: '0.68rem', fontWeight: 700 }}
                        />
                      )}
                    </Stack>

                    <Box sx={{ fontSize: '0.78rem', color: '#475569', mb: 1.5, flexGrow: 1 }}>
                      <div>
                        <strong>Started:</strong>{' '}
                        {stage.started_at ? new Date(stage.started_at).toLocaleTimeString() : '—'}
                      </div>
                      <div>
                        <strong>Completed:</strong>{' '}
                        {stage.completed_at ? new Date(stage.completed_at).toLocaleTimeString() : '—'}
                      </div>
                      <div>
                        <strong>Duration:</strong>{' '}
                        {stage.duration_seconds != null ? `${stage.duration_seconds.toFixed(3)} s` : '—'}
                      </div>
                    </Box>

                    {stage.warnings && stage.warnings.length > 0 && (
                      <Alert severity="warning" sx={{ py: 0.2, px: 1, mb: 1, '& .MuiAlert-message': { fontSize: '0.74rem' } }}>
                        {stage.warnings[0]}
                      </Alert>
                    )}

                    {stage.error_message && (
                      <Alert severity="error" sx={{ py: 0.2, px: 1, mb: 1, '& .MuiAlert-message': { fontSize: '0.74rem' } }}>
                        {stage.error_message}
                      </Alert>
                    )}

                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ pt: 1, borderTop: '1px solid #F1F5F9' }}>
                      <Button
                        size="small"
                        onClick={() => setSelectedStage(stage)}
                        disabled={!stage.output}
                      >
                        Inspect Output
                      </Button>
                      {stage.id && (
                        <Button
                          size="small"
                          startIcon={<ReplayIcon fontSize="small" />}
                          disabled={retryStageMut.isPending}
                          onClick={() => retryStageMut.mutate(stage.id!)}
                        >
                          Retry Stage
                        </Button>
                      )}
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {liveEvents.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Real-Time SSE Event Stream
                </Typography>
                <Stack spacing={0.5}>
                  {liveEvents.slice(0, 6).map((ev, idx) => (
                    <Typography key={idx} variant="caption" sx={{ fontFamily: 'monospace', color: '#334155' }}>
                      [{ev.timestamp || 'live'}] {ev.event} — Stage {ev.stage_order || ''} {ev.stage_label || ''}: {ev.status || ''}
                    </Typography>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          )}
        </Stack>
      )}

      {/* Stage Output JSON Inspector Dialog */}
      <Dialog open={Boolean(selectedStage)} onClose={() => setSelectedStage(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Stage {selectedStage?.stage_order}: {selectedStage?.stage_label} — Output Telemetry
        </DialogTitle>
        <DialogContent dividers>
          {selectedStage && (
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <StatusBadge status={selectedStage.status} />
                <Typography variant="body2">
                  Provider: <strong>{selectedStage.provider}</strong> ({selectedStage.model_name}{' '}
                  {selectedStage.model_version})
                </Typography>
              </Stack>
              {selectedStage.warnings?.map((w, i) => (
                <Alert key={i} severity="warning">
                  {w}
                </Alert>
              ))}
              <Box
                component="pre"
                sx={{
                  p: 2,
                  borderRadius: 1.5,
                  backgroundColor: '#0F172A',
                  color: '#E2E8F0',
                  fontSize: '0.78rem',
                  overflowX: 'auto',
                  maxHeight: 380,
                }}
              >
                {JSON.stringify(selectedStage.output || {}, null, 2)}
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedStage(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 9: Landmark Review and Manual Correction Workspace
// ============================================================================
export const LandmarkReviewWorkspacePage: React.FC = () => {
  const { visitId } = useParams<{ visitId: string }>();
  const queryClient = useQueryClient();
  const activeVisitId = useAuthStore((s) => s.activeContext.visitId);
  const resolvedVisitId = visitId || activeVisitId || '';

  const [selectedVisitId, setSelectedVisitId] = useState<string>(resolvedVisitId);
  const [selectedImageType, setSelectedImageType] = useState<string>('Frontal');
  const [selectedLandmarkId, setSelectedLandmarkId] = useState<string | null>(null);

  // Interactive viewer controls
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [showAIPredicted, setShowAIPredicted] = useState<boolean>(true);
  const [showExaminerAdjusted, setShowExaminerAdjusted] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);

  // Dragging & Inspector state
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [draggingLandmarkId, setDraggingLandmarkId] = useState<string | null>(null);
  const [draftCoords, setDraftCoords] = useState<{ x: number; y: number } | null>(null);
  const [correctionReason, setCorrectionReason] = useState<string>(
    'Manual anatomical refinement by clinical examiner'
  );
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Add Missing Landmark Dialog
  const [addOpen, setAddOpen] = useState<boolean>(false);
  const [addCode, setAddCode] = useState<string>('Gn');
  const [addX, setAddX] = useState<number>(400);
  const [addY, setAddY] = useState<number>(640);
  const [addReason, setAddReason] = useState<string>('Added missing protocol landmark on review');

  const visitsQuery = useQuery({
    queryKey: ['visits-for-landmarks'],
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

  const landmarksQuery = useQuery({
    queryKey: ['visit-landmarks', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/landmarks/visits/${selectedVisitId}`);
      return res.data.data as {
        visit_id: string;
        images: Array<VisitImageRecord & { file_url: string }>;
        by_image_type: Record<string, LandmarkRecord[]>;
        landmarks: LandmarkRecord[];
      };
    },
  });

  const definitionsQuery = useQuery({
    queryKey: ['landmark-definitions'],
    queryFn: async () => {
      const res = await api.get('/landmarks/definitions');
      return res.data.data as Array<{
        id: string;
        code: string;
        name: string;
        side: string;
        landmark_type: string;
      }>;
    },
  });

  const activeImage = useMemo(() => {
    const imgs = landmarksQuery.data?.images || [];
    return imgs.find((i) => i.image_type === selectedImageType) || imgs[0] || null;
  }, [landmarksQuery.data, selectedImageType]);

  const currentLandmarks = useMemo(() => {
    if (!landmarksQuery.data || !activeImage) return [];
    return landmarksQuery.data.by_image_type[activeImage.image_type] || [];
  }, [landmarksQuery.data, activeImage]);

  const selectedLandmark = useMemo(() => {
    if (!currentLandmarks.length) return null;
    return currentLandmarks.find((l) => l.id === selectedLandmarkId) || currentLandmarks[0];
  }, [currentLandmarks, selectedLandmarkId]);

  useEffect(() => {
    if (selectedLandmark) {
      setSelectedLandmarkId(selectedLandmark.id);
      setDraftCoords({
        x: selectedLandmark.effective_x ?? selectedLandmark.predicted_x ?? 400,
        y: selectedLandmark.effective_y ?? selectedLandmark.predicted_y ?? 400,
      });
    } else {
      setDraftCoords(null);
    }
  }, [selectedLandmark?.id]);

  const adjustMut = useMutation({
    mutationFn: async (payload: {
      landmarkId: string;
      corrected_x: number | null;
      corrected_y: number | null;
      review_status: string;
      correction_reason: string;
    }) => {
      const res = await api.put(`/landmarks/${payload.landmarkId}/adjust`, {
        corrected_x: payload.corrected_x,
        corrected_y: payload.corrected_y,
        review_status: payload.review_status,
        correction_reason: payload.correction_reason,
      });
      return res.data.data as LandmarkRecord;
    },
    onSuccess: (updated) => {
      setFeedback({
        type: 'success',
        text: `Landmark ${updated.code} (${updated.name}) saved with status '${updated.status}'. Original AI coordinates preserved.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-landmarks', selectedVisitId] });
      queryClient.invalidateQueries({ queryKey: ['visit-measurements', selectedVisitId] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const approveAllMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/landmarks/visits/${selectedVisitId}/approve-all`, {
        image_type: activeImage?.image_type || null,
        reason: 'Batch approved by examiner after visual inspection',
      });
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: `Approved ${res.approved_count} landmarks for ${activeImage?.image_type || 'visit'}.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-landmarks', selectedVisitId] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const addLandmarkMut = useMutation({
    mutationFn: async () => {
      if (!activeImage) throw new Error('No active image');
      const res = await api.post(`/landmarks/images/${activeImage.id}`, {
        code: addCode,
        x: Number(addX),
        y: Number(addY),
        reason: addReason,
      });
      return res.data.data;
    },
    onSuccess: () => {
      setAddOpen(false);
      setFeedback({ type: 'success', text: `Permitted landmark ${addCode} added to ${activeImage?.image_type}.` });
      queryClient.invalidateQueries({ queryKey: ['visit-landmarks', selectedVisitId] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const imgWidth = activeImage?.width || (activeImage?.image_type === 'OPG' ? 1200 : 800);
  const imgHeight = activeImage?.height || (activeImage?.image_type === 'OPG' ? 720 : 900);

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggingLandmarkId || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * imgWidth;
    const relY = ((e.clientY - rect.top) / rect.height) * imgHeight;
    const clampedX = Math.max(0, Math.min(imgWidth, Math.round(relX * 10) / 10));
    const clampedY = Math.max(0, Math.min(imgHeight, Math.round(relY * 10) / 10));
    setDraftCoords({ x: clampedX, y: clampedY });
  };

  const handleSvgMouseUp = () => {
    if (draggingLandmarkId) {
      setDraggingLandmarkId(null);
    }
  };

  const activeVisitObj = (visitsQuery.data || []).find((v) => v.id === selectedVisitId);

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
        title="Landmark Review & Manual Correction Workspace"
        subtitle="Inspect AI-predicted anatomical & OPG landmarks, drag to refine coordinates without overwriting AI predictions, or mark occluded landmarks Not Identifiable"
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
              startIcon={<AddLocationAltIcon />}
              disabled={!activeImage}
              onClick={() => setAddOpen(true)}
            >
              Add Permitted Landmark
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<CheckCircleIcon />}
              disabled={!activeImage || approveAllMut.isPending}
              onClick={() => approveAllMut.mutate()}
            >
              Approve All ({activeImage?.image_type || 'View'})
            </Button>
          </>
        }
      />

      {feedback && (
        <Alert severity={feedback.type} sx={{ mb: 2 }} onClose={() => setFeedback(null)}>
          {feedback.text}
        </Alert>
      )}

      {landmarksQuery.isLoading ? (
        <LoadingSkeleton rows={7} />
      ) : landmarksQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(landmarksQuery.error)}
          onRetry={() => landmarksQuery.refetch()}
        />
      ) : (
        <Grid container spacing={2}>
          {/* LEFT PANEL: Image View Selector + Landmark List */}
          <Grid size={{ xs: 12, lg: 3.5 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  1. Image View Selector
                </Typography>
                <Stack direction="row" spacing={0.8} flexWrap="wrap" sx={{ mb: 2 }}>
                  {(['Frontal', 'RightLateral', 'LeftLateral', 'OPG'] as const).map((vtype) => {
                    const count = (landmarksQuery.data?.by_image_type[vtype] || []).length;
                    return (
                      <Button
                        key={vtype}
                        size="small"
                        variant={selectedImageType === vtype ? 'contained' : 'outlined'}
                        onClick={() => setSelectedImageType(vtype)}
                        sx={{ mb: 0.5 }}
                      >
                        {vtype} ({count})
                      </Button>
                    );
                  })}
                </Stack>

                {activeImage && (
                  <Box
                    sx={{
                      p: 1.2,
                      mb: 1.5,
                      borderRadius: 1.5,
                      backgroundColor: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                      fontSize: '0.76rem',
                    }}
                  >
                    <div>
                      <strong>Filename:</strong> {activeImage.original_filename}
                    </div>
                    <div>
                      <strong>Dimensions:</strong> {imgWidth} × {imgHeight} px
                    </div>
                    <div>
                      <strong>Source Type:</strong>{' '}
                      {activeImage.is_synthetic ? 'Synthetic Research Image' : 'Clinical Upload'}
                    </div>
                  </Box>
                )}

                <Divider sx={{ my: 1.5 }} />

                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  2. Anatomical Landmarks ({currentLandmarks.length})
                </Typography>

                <TableContainer sx={{ maxHeight: 470 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Landmark</TableCell>
                        <TableCell>Conf.</TableCell>
                        <TableCell>Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {currentLandmarks.map((lm) => {
                        const isSelected = lm.id === selectedLandmark?.id;
                        return (
                          <TableRow
                            key={lm.id}
                            hover
                            selected={isSelected}
                            onClick={() => setSelectedLandmarkId(lm.id)}
                            sx={{ cursor: 'pointer' }}
                          >
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                {lm.code}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {lm.name} ({lm.side})
                              </Typography>
                            </TableCell>
                            <TableCell>
                              {lm.confidence != null ? `${Math.round(lm.confidence * 100)}%` : '—'}
                            </TableCell>
                            <TableCell>
                              <StatusBadge status={lm.status} />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* CENTER PANEL: Interactive SVG/Canvas Landmark Viewer */}
          <Grid size={{ xs: 12, lg: 5 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Stack
                  direction="row"
                  justifyContent="space-between"
                  alignItems="center"
                  flexWrap="wrap"
                  spacing={1}
                  sx={{ mb: 1.5 }}
                >
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Tooltip title="Zoom In">
                      <IconButton size="small" onClick={() => setZoom((z) => Math.min(2.5, z + 0.25))}>
                        <ZoomInIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Zoom Out">
                      <IconButton size="small" onClick={() => setZoom((z) => Math.max(0.6, z - 0.25))}>
                        <ZoomOutIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Fit to Screen">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setZoom(1);
                          setPan({ x: 0, y: 0 });
                        }}
                      >
                        <FitScreenIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Chip size="small" label={`Zoom: ${Math.round(zoom * 100)}%`} />
                  </Stack>

                  <Stack direction="row" spacing={1} alignItems="center">
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={showAIPredicted}
                          onChange={(e) => setShowAIPredicted(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">AI Predicted (Purple)</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={showExaminerAdjusted}
                          onChange={(e) => setShowExaminerAdjusted(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">Examiner / Active (Teal)</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={showLabels}
                          onChange={(e) => setShowLabels(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">Labels</Typography>}
                    />
                  </Stack>
                </Stack>

                {!activeImage ? (
                  <EmptyState title="No image uploaded for this view" />
                ) : (
                  <Box
                    sx={{
                      position: 'relative',
                      width: '100%',
                      height: 540,
                      overflow: 'auto',
                      backgroundColor: '#0F172A',
                      borderRadius: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '1px solid #334155',
                    }}
                  >
                    <Box
                      sx={{
                        transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
                        transformOrigin: 'center center',
                        transition: draggingLandmarkId ? 'none' : 'transform 0.1s ease',
                        width: '100%',
                        maxWidth: activeImage.image_type === 'OPG' ? 680 : 460,
                      }}
                    >
                      <svg
                        ref={svgRef}
                        viewBox={`0 0 ${imgWidth} ${imgHeight}`}
                        style={{
                          width: '100%',
                          height: 'auto',
                          display: 'block',
                          userSelect: 'none',
                          cursor: draggingLandmarkId ? 'grabbing' : 'crosshair',
                        }}
                        onMouseMove={handleSvgMouseMove}
                        onMouseUp={handleSvgMouseUp}
                      >
                        <image
                          href={withAuthTokenUrl(activeImage.file_url)}
                          width={imgWidth}
                          height={imgHeight}
                        />

                        {currentLandmarks.map((lm) => {
                          const isSelected = lm.id === selectedLandmark?.id;
                          const predX = lm.predicted_x;
                          const predY = lm.predicted_y;
                          const activeX =
                            isSelected && draftCoords
                              ? draftCoords.x
                              : lm.effective_x ?? lm.predicted_x;
                          const activeY =
                            isSelected && draftCoords
                              ? draftCoords.y
                              : lm.effective_y ?? lm.predicted_y;

                          if (lm.status === 'NotIdentifiable') return null;

                          return (
                            <g key={lm.id}>
                              {/* Connector vector between AI prediction and Examiner adjustment */}
                              {showAIPredicted &&
                                showExaminerAdjusted &&
                                predX != null &&
                                predY != null &&
                                activeX != null &&
                                activeY != null &&
                                (Math.abs(predX - activeX) > 0.5 || Math.abs(predY - activeY) > 0.5) && (
                                  <line
                                    x1={predX}
                                    y1={predY}
                                    x2={activeX}
                                    y2={activeY}
                                    stroke="#F59E0B"
                                    strokeWidth={2}
                                    strokeDasharray="4 2"
                                  />
                                )}

                              {/* Original AI Prediction Marker (never overwritten) */}
                              {showAIPredicted && predX != null && predY != null && (
                                <circle
                                  cx={predX}
                                  cy={predY}
                                  r={isSelected ? 7 : 5}
                                  fill="#A855F7"
                                  fillOpacity={0.75}
                                  stroke="#FFFFFF"
                                  strokeWidth={1.5}
                                  onClick={() => setSelectedLandmarkId(lm.id)}
                                />
                              )}

                              {/* Active / Examiner Draggable Marker */}
                              {showExaminerAdjusted && activeX != null && activeY != null && (
                                <g
                                  style={{ cursor: 'grab' }}
                                  onMouseDown={(e) => {
                                    e.stopPropagation();
                                    setSelectedLandmarkId(lm.id);
                                    setDraggingLandmarkId(lm.id);
                                  }}
                                >
                                  <circle
                                    cx={activeX}
                                    cy={activeY}
                                    r={isSelected ? 10 : 7}
                                    fill={lm.examiner_x != null ? '#10B981' : '#087E8B'}
                                    stroke={isSelected ? '#FACC15' : '#FFFFFF'}
                                    strokeWidth={isSelected ? 3 : 1.8}
                                  />
                                  {showLabels && (
                                    <text
                                      x={activeX + 12}
                                      y={activeY + 4}
                                      fill="#FFFFFF"
                                      fontSize={imgWidth > 900 ? '18' : '15'}
                                      fontWeight="700"
                                      style={{
                                        textShadow: '0px 1px 4px rgba(0,0,0,0.95)',
                                        pointerEvents: 'none',
                                      }}
                                    >
                                      {lm.code}
                                    </text>
                                  )}
                                </g>
                              )}
                            </g>
                          );
                        })}
                      </svg>
                    </Box>
                  </Box>
                )}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Tip: Click or drag any landmark marker on the canvas to refine its coordinates. Original AI coordinates (purple) are permanently preserved alongside examiner adjustments (teal/green).
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* RIGHT PANEL: Selected Landmark Inspector & Dual-Coordinate Audit Trail */}
          <Grid size={{ xs: 12, lg: 3.5 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
                  3. Selected Landmark Inspector
                </Typography>

                {!selectedLandmark ? (
                  <EmptyState title="Select a landmark to inspect or adjust" />
                ) : (
                  <Stack spacing={2}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 1.5,
                        backgroundColor: '#F8FAFC',
                        border: '1px solid #E2E8F0',
                      }}
                    >
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#123B50' }}>
                          {selectedLandmark.code} — {selectedLandmark.name}
                        </Typography>
                        <StatusBadge status={selectedLandmark.status} />
                      </Stack>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.4 }}>
                        Region: {selectedLandmark.anatomical_region} • Side: {selectedLandmark.side} • Type:{' '}
                        {selectedLandmark.landmark_type}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        Model: {selectedLandmark.model_name || 'Manual'} ({selectedLandmark.model_version || 'v1'}) •
                        Confidence:{' '}
                        {selectedLandmark.confidence != null
                          ? `${(selectedLandmark.confidence * 100).toFixed(1)}%`
                          : 'N/A'}
                      </Typography>
                    </Box>

                    {/* Immutable AI Prediction Box */}
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 1.5,
                        backgroundColor: '#FAF5FF',
                        border: '1px solid #E9D5FF',
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#6B21A8', display: 'block' }}>
                        ORIGINAL AI-PREDICTED COORDINATES (IMMUTABLE)
                      </Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600, mt: 0.5 }}>
                        X: {selectedLandmark.predicted_x != null ? `${selectedLandmark.predicted_x.toFixed(1)} px` : 'None'}{' '}
                        | Y:{' '}
                        {selectedLandmark.predicted_y != null ? `${selectedLandmark.predicted_y.toFixed(1)} px` : 'None'}
                      </Typography>
                    </Box>

                    {/* Examiner Adjustment Inputs */}
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 1.5,
                        backgroundColor: '#F0FDFA',
                        border: '1px solid #99F6E4',
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#0F766E', display: 'block', mb: 1 }}>
                        EXAMINER-ADJUSTED COORDINATES (PX)
                      </Typography>
                      <Stack direction="row" spacing={1.5}>
                        <TextField
                          label="Adjusted X (px)"
                          type="number"
                          size="small"
                          fullWidth
                          value={draftCoords?.x ?? ''}
                          onChange={(e) =>
                            setDraftCoords((prev) => ({
                              x: Number(e.target.value),
                              y: prev?.y ?? 0,
                            }))
                          }
                        />
                        <TextField
                          label="Adjusted Y (px)"
                          type="number"
                          size="small"
                          fullWidth
                          value={draftCoords?.y ?? ''}
                          onChange={(e) =>
                            setDraftCoords((prev) => ({
                              x: prev?.x ?? 0,
                              y: Number(e.target.value),
                            }))
                          }
                        />
                      </Stack>
                    </Box>

                    <TextField
                      label="Correction / Review Reason (Required for Audit Trail)"
                      size="small"
                      multiline
                      rows={2}
                      fullWidth
                      value={correctionReason}
                      onChange={(e) => setCorrectionReason(e.target.value)}
                    />

                    <Stack spacing={1}>
                      <Button
                        variant="contained"
                        color="primary"
                        disabled={adjustMut.isPending || !draftCoords}
                        onClick={() =>
                          adjustMut.mutate({
                            landmarkId: selectedLandmark.id,
                            corrected_x: draftCoords?.x ?? null,
                            corrected_y: draftCoords?.y ?? null,
                            review_status: 'Adjusted',
                            correction_reason: correctionReason,
                          })
                        }
                      >
                        Save Examiner Adjustment
                      </Button>

                      <Stack direction="row" spacing={1}>
                        <Button
                          fullWidth
                          variant="contained"
                          color="secondary"
                          startIcon={<CheckCircleIcon />}
                          disabled={adjustMut.isPending}
                          onClick={() =>
                            adjustMut.mutate({
                              landmarkId: selectedLandmark.id,
                              corrected_x: draftCoords?.x ?? selectedLandmark.effective_x,
                              corrected_y: draftCoords?.y ?? selectedLandmark.effective_y,
                              review_status: 'Approved',
                              correction_reason: correctionReason || 'Approved by examiner',
                            })
                          }
                        >
                          Approve
                        </Button>
                        <Button
                          fullWidth
                          variant="outlined"
                          color="error"
                          startIcon={<VisibilityOffIcon />}
                          disabled={adjustMut.isPending}
                          onClick={() =>
                            adjustMut.mutate({
                              landmarkId: selectedLandmark.id,
                              corrected_x: null,
                              corrected_y: null,
                              review_status: 'NotIdentifiable',
                              correction_reason:
                                correctionReason || 'Landmark occluded or not identifiable on view',
                            })
                          }
                        >
                          Not Identifiable
                        </Button>
                      </Stack>
                    </Stack>

                    <Divider />

                    <Box>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#475569', display: 'block', mb: 0.8 }}>
                        LANDMARK REVIEW HISTORY ({selectedLandmark.reviews.length})
                      </Typography>
                      {selectedLandmark.reviews.length === 0 ? (
                        <Typography variant="caption" color="text.secondary">
                          No manual adjustments recorded yet.
                        </Typography>
                      ) : (
                        <Stack spacing={1} sx={{ maxHeight: 160, overflowY: 'auto' }}>
                          {selectedLandmark.reviews.map((rev) => (
                            <Box
                              key={rev.id}
                              sx={{
                                p: 1,
                                borderRadius: 1,
                                backgroundColor: '#F8FAFC',
                                border: '1px solid #E2E8F0',
                                fontSize: '0.73rem',
                              }}
                            >
                              <div>
                                <strong>{rev.review_status}</strong> by {rev.reviewer_email}
                              </div>
                              <div>
                                Orig: ({rev.original_x?.toFixed(1) ?? '—'}, {rev.original_y?.toFixed(1) ?? '—'}) →
                                New: ({rev.corrected_x?.toFixed(1) ?? '—'}, {rev.corrected_y?.toFixed(1) ?? '—'})
                              </div>
                              {rev.correction_reason && (
                                <div style={{ color: '#475569' }}>Reason: {rev.correction_reason}</div>
                              )}
                            </Box>
                          ))}
                        </Stack>
                      )}
                    </Box>
                  </Stack>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Add Missing Protocol Landmark Dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Add Permitted Protocol Landmark</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <FormControl size="small" fullWidth>
              <InputLabel>Protocol Landmark</InputLabel>
              <Select
                label="Protocol Landmark"
                value={addCode}
                onChange={(e) => setAddCode(e.target.value)}
              >
                {(definitionsQuery.data || []).map((d) => (
                  <MenuItem key={d.id} value={d.code}>
                    {d.code} — {d.name} ({d.landmark_type})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Stack direction="row" spacing={1.5}>
              <TextField
                label="X Coordinate (px)"
                type="number"
                size="small"
                fullWidth
                value={addX}
                onChange={(e) => setAddX(Number(e.target.value))}
              />
              <TextField
                label="Y Coordinate (px)"
                type="number"
                size="small"
                fullWidth
                value={addY}
                onChange={(e) => setAddY(Number(e.target.value))}
              />
            </Stack>
            <TextField
              label="Reason"
              size="small"
              fullWidth
              value={addReason}
              onChange={(e) => setAddReason(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => addLandmarkMut.mutate()} disabled={addLandmarkMut.isPending}>
            Add Landmark
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
