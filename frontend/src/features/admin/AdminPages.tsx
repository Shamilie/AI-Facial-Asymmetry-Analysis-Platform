import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid2 as Grid,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
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
import NetworkCheckIcon from '@mui/icons-material/NetworkCheck';
import ScienceIcon from '@mui/icons-material/Science';
import ReplayIcon from '@mui/icons-material/Replay';
import CancelIcon from '@mui/icons-material/Cancel';
import LockResetIcon from '@mui/icons-material/LockReset';
import SecurityIcon from '@mui/icons-material/Security';
import PublishIcon from '@mui/icons-material/Publish';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import MenuBookOutlinedIcon from '@mui/icons-material/MenuBookOutlined';
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import PrintOutlinedIcon from '@mui/icons-material/PrintOutlined';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import OpenInNewOutlinedIcon from '@mui/icons-material/OpenInNewOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import StraightenOutlinedIcon from '@mui/icons-material/StraightenOutlined';
import ViewInArOutlinedIcon from '@mui/icons-material/ViewInArOutlined';
import CompareArrowsOutlinedIcon from '@mui/icons-material/CompareArrowsOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage } from '@/services/api';
import {
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingSkeleton,
  PageHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { useAuthStore } from '@/store/authStore';

// ============================================================================
// PAGE 14: AI Model Configuration and Provider Management
// ============================================================================
export const AIModelConfigPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedTaskFilter, setSelectedTaskFilter] = useState<string>('');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [addOpen, setAddOpen] = useState<boolean>(false);
  const [newProvider, setNewProvider] = useState({
    task_type: 'FacialLandmarks',
    provider_name: 'CustomGPU',
    display_name: 'Custom HRNet Landmark Endpoint',
    model_name: 'hrnet-w18-facial-21pt',
    model_version: 'v1.2.0',
    endpoint_url: 'http://localhost:8085/v1/infer',
    api_key_env_var: 'CUSTOM_GPU_TOKEN',
    confidence_threshold: 0.75,
    timeout_seconds: 30,
    max_retries: 2,
    fallback_provider: 'Demo',
    is_enabled: true,
    is_default: false,
    allow_external_upload: false,
  });

  const providersQuery = useQuery({
    queryKey: ['ai-providers-config'],
    queryFn: async () => {
      const res = await api.get('/ai/providers');
      return res.data.data as {
        allow_external_ai_uploads_env: boolean;
        providers: Array<{
          id: string;
          task_type: string;
          provider_name: string;
          display_name: string;
          model_name: string;
          model_version: string;
          endpoint_url: string | null;
          api_key_env_var: string | null;
          api_key_configured: boolean;
          local_model_path: string | null;
          device_preference: string;
          confidence_threshold: number;
          timeout_seconds: number;
          max_retries: number;
          fallback_provider: string | null;
          is_enabled: boolean;
          is_default: boolean;
          is_demo: boolean;
          allow_external_upload: boolean;
          health_status: string;
          last_tested_at: string | null;
        }>;
      };
    },
  });

  const testConnMut = useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/ai/providers/${id}/test-connection`);
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: res.ok ? 'success' : 'error',
        text: `Connection Check (${res.provider_name} / ${res.model_name}): ${res.message}`,
      });
      queryClient.invalidateQueries({ queryKey: ['ai-providers-config'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const testInferMut = useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/ai/providers/${id}/test-inference`);
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: `Test Inference Succeeded (${res.provider} / ${res.model_name} ${res.model_version}) in ${res.duration_seconds?.toFixed(3) ?? 0}s.`,
      });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const updateProviderMut = useMutation({
    mutationFn: async (payload: { id: string; body: Record<string, any> }) => {
      const res = await api.put(`/ai/providers/${payload.id}`, payload.body);
      return res.data.data;
    },
    onSuccess: () => {
      setFeedback({ type: 'success', text: 'AI Provider configuration updated.' });
      queryClient.invalidateQueries({ queryKey: ['ai-providers-config'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const createProviderMut = useMutation({
    mutationFn: async () => {
      const res = await api.post('/ai/providers', newProvider);
      return res.data.data;
    },
    onSuccess: () => {
      setAddOpen(false);
      setFeedback({ type: 'success', text: 'New task-specific AI provider adapter registered.' });
      queryClient.invalidateQueries({ queryKey: ['ai-providers-config'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const providers = (providersQuery.data?.providers || []).filter(
    (p) => !selectedTaskFilter || p.task_type === selectedTaskFilter
  );

  return (
    <Box>
      <PageHeader
        title="AI Model Configuration & Provider Adapter Registry"
        subtitle="Manage task-specific AI providers (MediaPipe, OpenAI, NVIDIA NIM/Triton, Custom GPU, Local PyTorch/ONNX, and Demo) with strict privacy controls"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 230, backgroundColor: '#FFF' }}>
              <InputLabel>Filter by AI Task</InputLabel>
              <Select
                label="Filter by AI Task"
                value={selectedTaskFilter}
                onChange={(e) => setSelectedTaskFilter(e.target.value)}
              >
                <MenuItem value="">All 7 Pipeline Tasks</MenuItem>
                <MenuItem value="ImageQuality">ImageQuality</MenuItem>
                <MenuItem value="FacialLandmarks">FacialLandmarks</MenuItem>
                <MenuItem value="FacialSegmentation">FacialSegmentation</MenuItem>
                <MenuItem value="Reconstruction3D">Reconstruction3D</MenuItem>
                <MenuItem value="OPGLandmarks">OPGLandmarks</MenuItem>
                <MenuItem value="OPGSegmentation">OPGSegmentation</MenuItem>
                <MenuItem value="ReportGeneration">ReportGeneration</MenuItem>
              </Select>
            </FormControl>
            <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
              Register Provider Adapter
            </Button>
          </>
        }
      />

      <Alert
        severity={providersQuery.data?.allow_external_ai_uploads_env ? 'warning' : 'info'}
        sx={{ mb: 2 }}
      >
        <strong>Clinical Image Privacy Guard (`ALLOW_EXTERNAL_AI_UPLOADS`):</strong> Currently{' '}
        <strong>{providersQuery.data?.allow_external_ai_uploads_env ? 'ENABLED' : 'DISABLED (Default)'}</strong>.
        Identifiable patient photographs and OPG radiographs are blocked from being transmitted to external cloud APIs unless both the server environment flag and provider policy explicitly allow external uploads. API keys are resolved exclusively from backend environment variables and never exposed to the browser.
      </Alert>

      {feedback && (
        <Alert severity={feedback.type} sx={{ mb: 2 }} onClose={() => setFeedback(null)}>
          {feedback.text}
        </Alert>
      )}

      {providersQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : providersQuery.isError ? (
        <ErrorState message={extractErrorMessage(providersQuery.error)} onRetry={() => providersQuery.refetch()} />
      ) : (
        <Card>
          <CardContent sx={{ p: 0 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Task Type</TableCell>
                    <TableCell>Provider & Display Name</TableCell>
                    <TableCell>Model & Version</TableCell>
                    <TableCell>Endpoint / Secret Env</TableCell>
                    <TableCell>Conf. / Timeout</TableCell>
                    <TableCell>Health</TableCell>
                    <TableCell>Default</TableCell>
                    <TableCell>Enabled</TableCell>
                    <TableCell align="right">Validation Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {providers.map((p) => (
                    <TableRow key={p.id} hover>
                      <TableCell sx={{ fontWeight: 700, color: '#123B50' }}>{p.task_type}</TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={0.8} alignItems="center">
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {p.provider_name}
                          </Typography>
                          {p.is_demo && <Chip size="small" color="warning" label="DEMO" sx={{ fontSize: '0.65rem' }} />}
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                          {p.display_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                          {p.model_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {p.model_version} • Device: {p.device_preference}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" sx={{ display: 'block' }}>
                          {p.endpoint_url || p.local_model_path || 'Built-in Adapter'}
                        </Typography>
                        {p.api_key_env_var && (
                          <Chip
                            size="small"
                            variant="outlined"
                            label={`Env: ${p.api_key_env_var} (${p.api_key_configured ? 'Set' : 'Unset'})`}
                            sx={{ fontSize: '0.68rem', mt: 0.3 }}
                          />
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          ≥ {(p.confidence_threshold * 100).toFixed(0)}% • {p.timeout_seconds}s
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={p.health_status} />
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant={p.is_default ? 'contained' : 'outlined'}
                          color={p.is_default ? 'secondary' : 'inherit'}
                          onClick={() =>
                            updateProviderMut.mutate({
                              id: p.id,
                              body: { is_default: true, is_enabled: true },
                            })
                          }
                        >
                          {p.is_default ? 'Default' : 'Set Default'}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Switch
                          size="small"
                          checked={p.is_enabled}
                          onChange={(e) =>
                            updateProviderMut.mutate({
                              id: p.id,
                              body: { is_enabled: e.target.checked },
                            })
                          }
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={0.8} justifyContent="flex-end">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<NetworkCheckIcon fontSize="small" />}
                            onClick={() => testConnMut.mutate(p.id)}
                          >
                            Test Conn
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="secondary"
                            startIcon={<ScienceIcon fontSize="small" />}
                            onClick={() => testInferMut.mutate(p.id)}
                          >
                            Test Infer
                          </Button>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Register New Provider Modal */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Register Task-Specific AI Provider Adapter</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <Stack direction="row" spacing={1.5}>
              <FormControl size="small" fullWidth>
                <InputLabel>Task Type</InputLabel>
                <Select
                  label="Task Type"
                  value={newProvider.task_type}
                  onChange={(e) => setNewProvider({ ...newProvider, task_type: e.target.value })}
                >
                  <MenuItem value="ImageQuality">ImageQuality</MenuItem>
                  <MenuItem value="FacialLandmarks">FacialLandmarks</MenuItem>
                  <MenuItem value="FacialSegmentation">FacialSegmentation</MenuItem>
                  <MenuItem value="Reconstruction3D">Reconstruction3D</MenuItem>
                  <MenuItem value="OPGLandmarks">OPGLandmarks</MenuItem>
                  <MenuItem value="OPGSegmentation">OPGSegmentation</MenuItem>
                  <MenuItem value="ReportGeneration">ReportGeneration</MenuItem>
                </Select>
              </FormControl>

              <FormControl size="small" fullWidth>
                <InputLabel>Provider Family</InputLabel>
                <Select
                  label="Provider Family"
                  value={newProvider.provider_name}
                  onChange={(e) => setNewProvider({ ...newProvider, provider_name: e.target.value })}
                >
                  <MenuItem value="MediaPipe">MediaPipe</MenuItem>
                  <MenuItem value="Gemini">Google Gemini API</MenuItem>
                  <MenuItem value="OpenAI">OpenAI</MenuItem>
                  <MenuItem value="NVIDIA">NVIDIA NIM / Triton</MenuItem>
                  <MenuItem value="CustomGPU">CustomGPU</MenuItem>
                  <MenuItem value="LocalModel">LocalModel (PyTorch/ONNX)</MenuItem>
                  <MenuItem value="Demo">Demo (Synthetic Fallback)</MenuItem>
                </Select>
              </FormControl>
            </Stack>

            <TextField
              label="Display Name"
              size="small"
              fullWidth
              value={newProvider.display_name}
              onChange={(e) => setNewProvider({ ...newProvider, display_name: e.target.value })}
            />

            <Stack direction="row" spacing={1.5}>
              <TextField
                label="Model Identifier"
                size="small"
                fullWidth
                value={newProvider.model_name}
                onChange={(e) => setNewProvider({ ...newProvider, model_name: e.target.value })}
              />
              <TextField
                label="Model Version"
                size="small"
                fullWidth
                value={newProvider.model_version}
                onChange={(e) => setNewProvider({ ...newProvider, model_version: e.target.value })}
              />
            </Stack>

            <TextField
              label="Inference Endpoint URL"
              size="small"
              fullWidth
              value={newProvider.endpoint_url}
              onChange={(e) => setNewProvider({ ...newProvider, endpoint_url: e.target.value })}
            />

            <TextField
              label="Backend Environment Variable Name for API Key (Never enter raw secrets)"
              size="small"
              fullWidth
              value={newProvider.api_key_env_var}
              onChange={(e) => setNewProvider({ ...newProvider, api_key_env_var: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createProviderMut.mutate()} disabled={createProviderMut.isPending}>
            Save Adapter
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 15: AI Execution Monitor and Job Queue
// ============================================================================
export const AIExecutionMonitorPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [taskFilter, setTaskFilter] = useState<string>('');
  const [selectedJob, setSelectedJob] = useState<Record<string, any> | null>(null);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const monitorQuery = useQuery({
    queryKey: ['ai-execution-monitor', statusFilter, taskFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      if (taskFilter) params.set('task_type', taskFilter);
      const res = await api.get(`/ai/jobs?${params.toString()}`);
      return res.data.data as {
        kpis: {
          queued_jobs: number;
          running_jobs: number;
          completed_jobs: number;
          failed_jobs: number;
          average_runtime_seconds: number;
          manual_review_queue: number;
        };
        items: Array<Record<string, any>>;
      };
    },
  });

  const retryMut = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await api.post(`/ai/jobs/${jobId}/retry`);
      return res.data.data;
    },
    onSuccess: () => {
      setMsg({ type: 'success', text: 'Job re-dispatched and completed.' });
      queryClient.invalidateQueries({ queryKey: ['ai-execution-monitor'] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const cancelMut = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await api.post(`/ai/jobs/${jobId}/cancel`);
      return res.data.data;
    },
    onSuccess: () => {
      setMsg({ type: 'success', text: 'Job cancelled.' });
      queryClient.invalidateQueries({ queryKey: ['ai-execution-monitor'] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const kpis = monitorQuery.data?.kpis;

  return (
    <Box>
      <PageHeader
        title="AI Execution Monitor & Job Queue"
        subtitle="Real-time telemetry across all asynchronous and inline AI inference stages, execution durations, and retry controls"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 180, backgroundColor: '#FFF' }}>
              <InputLabel>Job Status</InputLabel>
              <Select
                label="Job Status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="Completed">Completed</MenuItem>
                <MenuItem value="Processing">Processing</MenuItem>
                <MenuItem value="Queued">Queued</MenuItem>
                <MenuItem value="Failed">Failed</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 200, backgroundColor: '#FFF' }}>
              <InputLabel>Task Type</InputLabel>
              <Select
                label="Task Type"
                value={taskFilter}
                onChange={(e) => setTaskFilter(e.target.value)}
              >
                <MenuItem value="">All Pipeline Tasks</MenuItem>
                <MenuItem value="ImageQuality">ImageQuality</MenuItem>
                <MenuItem value="FacialLandmarks">FacialLandmarks</MenuItem>
                <MenuItem value="Reconstruction3D">Reconstruction3D</MenuItem>
                <MenuItem value="OPGLandmarks">OPGLandmarks</MenuItem>
                <MenuItem value="GeometryCalculation">GeometryCalculation</MenuItem>
                <MenuItem value="ReportGeneration">ReportGeneration</MenuItem>
              </Select>
            </FormControl>
          </>
        }
      />

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      {monitorQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : monitorQuery.isError ? (
        <ErrorState message={extractErrorMessage(monitorQuery.error)} onRetry={() => monitorQuery.refetch()} />
      ) : (
        <Stack spacing={2.5}>
          {kpis && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard label="Queued Jobs" value={kpis.queued_jobs} accent="#64748B" />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard label="Running Jobs" value={kpis.running_jobs} accent="#2563EB" />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard label="Completed Jobs" value={kpis.completed_jobs} accent="#16A34A" />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard label="Failed Jobs" value={kpis.failed_jobs} accent="#DC2626" />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Avg Stage Runtime"
                  value={`${kpis.average_runtime_seconds.toFixed(3)} s`}
                  accent="#087E8B"
                />
              </Grid>
              <Grid size={{ xs: 6, md: 2 }}>
                <KpiCard
                  label="Manual Review Queue"
                  value={kpis.manual_review_queue}
                  accent="#D97706"
                />
              </Grid>
            </Grid>
          )}

          <Card>
            <CardContent sx={{ p: 0 }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Patient / Visit</TableCell>
                      <TableCell>Stage & Task</TableCell>
                      <TableCell>Provider & Model</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Attempt</TableCell>
                      <TableCell>Runtime</TableCell>
                      <TableCell>Completed At</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(monitorQuery.data?.items || []).map((job) => (
                      <TableRow key={job.id} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {job.patient_code}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.visit_type}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            #{job.stage_order} — {job.stage_label}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.task_type}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{job.provider}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.model_name} ({job.model_version})
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={job.status} />
                        </TableCell>
                        <TableCell>#{job.attempt}</TableCell>
                        <TableCell>
                          {job.duration_seconds != null ? `${job.duration_seconds.toFixed(3)} s` : '—'}
                        </TableCell>
                        <TableCell>
                          {job.completed_at ? new Date(job.completed_at).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                            <Button size="small" onClick={() => setSelectedJob(job)}>
                              Logs
                            </Button>
                            <Button
                              size="small"
                              startIcon={<ReplayIcon fontSize="small" />}
                              onClick={() => retryMut.mutate(job.id)}
                            >
                              Retry
                            </Button>
                            {(job.status === 'Queued' || job.status === 'Processing') && (
                              <Button
                                size="small"
                                color="error"
                                startIcon={<CancelIcon fontSize="small" />}
                                onClick={() => cancelMut.mutate(job.id)}
                              >
                                Cancel
                              </Button>
                            )}
                          </Stack>
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

      <Dialog open={Boolean(selectedJob)} onClose={() => setSelectedJob(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Job Execution Telemetry — {selectedJob?.stage_label}
        </DialogTitle>
        <DialogContent dividers>
          <Box
            component="pre"
            sx={{
              p: 2,
              borderRadius: 1.5,
              backgroundColor: '#0F172A',
              color: '#E2E8F0',
              fontSize: '0.78rem',
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(selectedJob, null, 2)}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedJob(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 18: User Management and Role Administration
// ============================================================================
export const UserManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState<boolean>(false);
  const [newUser, setNewUser] = useState({
    email: '',
    first_name: '',
    last_name: '',
    password: 'Research@2026',
    roles: ['Clinician / Examiner'],
    is_active: true,
  });
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const usersQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const res = await api.get('/admin/users');
      return res.data.data as {
        users: Array<{
          id: string;
          email: string;
          first_name: string;
          last_name: string;
          full_name: string;
          is_active: boolean;
          roles: string[];
          primary_role: string;
          permissions: string[];
          last_login_at: string | null;
        }>;
        available_roles: Array<{
          id: string;
          name: string;
          description: string;
          permissions: string[];
        }>;
      };
    },
  });

  const createUserMut = useMutation({
    mutationFn: async () => {
      const res = await api.post('/admin/users', newUser);
      return res.data.data;
    },
    onSuccess: (u) => {
      setCreateOpen(false);
      setFeedback({ type: 'success', text: `Created user ${u.email} with role ${u.primary_role}.` });
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const [editUser, setEditUser] = useState<{
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    roles: string[];
    is_active: boolean;
  } | null>(null);

  const updateUserMut = useMutation({
    mutationFn: async (payload: {
      id: string;
      first_name?: string;
      last_name?: string;
      role_names?: string[];
      is_active?: boolean;
    }) => {
      const res = await api.put(`/admin/users/${payload.id}`, {
        first_name: payload.first_name,
        last_name: payload.last_name,
        role_names: payload.role_names,
        is_active: payload.is_active,
      });
      return res.data.data;
    },
    onSuccess: () => {
      setFeedback({ type: 'success', text: 'User details and assigned roles updated successfully.' });
      setEditUser(null);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const toggleUserMut = useMutation({
    mutationFn: async (payload: { id: string; is_active: boolean }) => {
      const res = await api.put(`/admin/users/${payload.id}`, { is_active: payload.is_active });
      return res.data.data;
    },
    onSuccess: () => {
      setFeedback({ type: 'success', text: 'Updated user active status.' });
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  const resetAccessMut = useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/admin/users/${id}/reset-access`, {});
      return res.data.data;
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: `Reset password for ${res.email} to temporary credential: ${res.temporary_password}`,
      });
    },
    onError: (err) => setFeedback({ type: 'error', text: extractErrorMessage(err) }),
  });

  return (
    <Box>
      <PageHeader
        title="User Management & Role-Based Access Control (RBAC)"
        subtitle="Administer clinical researchers, examiners, analysts, and system roles with backend-enforced permissions"
        actions={
          <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            Create Research User
          </Button>
        }
      />

      {feedback && (
        <Alert severity={feedback.type} sx={{ mb: 2 }} onClose={() => setFeedback(null)}>
          {feedback.text}
        </Alert>
      )}

      {usersQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : usersQuery.isError ? (
        <ErrorState message={extractErrorMessage(usersQuery.error)} onRetry={() => usersQuery.refetch()} />
      ) : (
        <Stack spacing={2.5}>
          <Card>
            <CardContent sx={{ p: 0 }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Full Name & Email</TableCell>
                      <TableCell>Assigned Role(s)</TableCell>
                      <TableCell>Granular Permissions</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Last Login</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(usersQuery.data?.users || []).map((u) => (
                      <TableRow key={u.id} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {u.full_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {u.email}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={0.5} flexWrap="wrap">
                            {u.roles.map((r) => (
                              <Chip key={r} size="small" color="primary" label={r} />
                            ))}
                          </Stack>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {u.permissions.length} permissions granted
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={u.is_active ? 'Active' : 'Rejected'} />
                        </TableCell>
                        <TableCell>
                          {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                        </TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<EditOutlinedIcon fontSize="small" />}
                              onClick={() =>
                                setEditUser({
                                  id: u.id,
                                  email: u.email,
                                  first_name: u.first_name || '',
                                  last_name: u.last_name || '',
                                  roles: u.roles || [],
                                  is_active: u.is_active,
                                })
                              }
                            >
                              Edit
                            </Button>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<LockResetIcon fontSize="small" />}
                              onClick={() => resetAccessMut.mutate(u.id)}
                            >
                              Reset Access
                            </Button>
                            <Button
                              size="small"
                              color={u.is_active ? 'error' : 'success'}
                              variant="outlined"
                              onClick={() =>
                                toggleUserMut.mutate({ id: u.id, is_active: !u.is_active })
                              }
                            >
                              {u.is_active ? 'Deactivate' : 'Activate'}
                            </Button>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          {/* Role Permission Matrix Card */}
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                6 Approved Research Roles & Permission Matrix
              </Typography>
              <Grid container spacing={2}>
                {(usersQuery.data?.available_roles || []).map((role) => (
                  <Grid key={role.id} size={{ xs: 12, md: 6, lg: 4 }}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        border: '1px solid #E2E8F0',
                        backgroundColor: '#F8FAFC',
                        height: '100%',
                      }}
                    >
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#123B50' }}>
                        {role.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                        {role.description}
                      </Typography>
                      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                        {role.permissions.map((perm) => (
                          <Chip
                            key={perm}
                            size="small"
                            variant="outlined"
                            label={perm}
                            sx={{ fontSize: '0.66rem' }}
                          />
                        ))}
                      </Stack>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Stack>
      )}

      {/* Create User Modal */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Create New Authorized User</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <TextField
              label="Email Address"
              size="small"
              fullWidth
              value={newUser.email}
              onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
            />
            <Stack direction="row" spacing={1.5}>
              <TextField
                label="First Name"
                size="small"
                fullWidth
                value={newUser.first_name}
                onChange={(e) => setNewUser({ ...newUser, first_name: e.target.value })}
              />
              <TextField
                label="Last Name"
                size="small"
                fullWidth
                value={newUser.last_name}
                onChange={(e) => setNewUser({ ...newUser, last_name: e.target.value })}
              />
            </Stack>
            <FormControl size="small" fullWidth>
              <InputLabel>Assigned Role</InputLabel>
              <Select
                label="Assigned Role"
                value={newUser.roles[0]}
                onChange={(e) => setNewUser({ ...newUser, roles: [e.target.value] })}
              >
                {(usersQuery.data?.available_roles || []).map((r) => (
                  <MenuItem key={r.id} value={r.name}>
                    {r.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Initial Password"
              size="small"
              fullWidth
              value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!newUser.email || createUserMut.isPending}
            onClick={() => createUserMut.mutate()}
          >
            Create User
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit User Details & Roles Modal */}
      <Dialog open={Boolean(editUser)} onClose={() => setEditUser(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Edit Research User & Assigned Role</DialogTitle>
        <DialogContent dividers>
          {editUser && (
            <Stack spacing={2} sx={{ mt: 0.5 }}>
              <TextField
                label="Email Address"
                size="small"
                fullWidth
                disabled
                value={editUser.email}
                helperText="Institutional email is identity-locked"
              />
              <Stack direction="row" spacing={1.5}>
                <TextField
                  label="First Name"
                  size="small"
                  fullWidth
                  value={editUser.first_name}
                  onChange={(e) => setEditUser({ ...editUser, first_name: e.target.value })}
                />
                <TextField
                  label="Last Name"
                  size="small"
                  fullWidth
                  value={editUser.last_name}
                  onChange={(e) => setEditUser({ ...editUser, last_name: e.target.value })}
                />
              </Stack>
              <FormControl size="small" fullWidth>
                <InputLabel>Assigned Role</InputLabel>
                <Select
                  label="Assigned Role"
                  value={editUser.roles[0] || ''}
                  onChange={(e) => setEditUser({ ...editUser, roles: [e.target.value] })}
                >
                  {(usersQuery.data?.available_roles || []).map((r) => (
                    <MenuItem key={r.id} value={r.name}>
                      {r.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControlLabel
                control={
                  <Switch
                    checked={editUser.is_active}
                    onChange={(e) => setEditUser({ ...editUser, is_active: e.target.checked })}
                  />
                }
                label="Account Active"
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditUser(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!editUser || updateUserMut.isPending}
            onClick={() => {
              if (editUser) {
                updateUserMut.mutate({
                  id: editUser.id,
                  first_name: editUser.first_name,
                  last_name: editUser.last_name,
                  role_names: editUser.roles,
                  is_active: editUser.is_active,
                });
              }
            }}
          >
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 19: Audit Logs Viewer (Append-Only Immutable Trail)
// ============================================================================
export const AuditLogsPage: React.FC = () => {
  const [actionFilter, setActionFilter] = useState<string>('');
  const [entityFilter, setEntityFilter] = useState<string>('');
  const [selectedAudit, setSelectedAudit] = useState<Record<string, any> | null>(null);

  const auditQuery = useQuery({
    queryKey: ['admin-audit-logs', actionFilter, entityFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '100' });
      if (actionFilter) params.set('action_type', actionFilter);
      if (entityFilter) params.set('entity_type', entityFilter);
      const res = await api.get(`/admin/audit-logs?${params.toString()}`);
      return res.data.data as {
        total: number;
        items: Array<{
          id: string;
          user_id: string | null;
          user_email: string;
          action_type: string;
          entity_type: string;
          entity_id: string | null;
          description: string;
          before_json: Record<string, any> | null;
          after_json: Record<string, any> | null;
          ip_address: string | null;
          created_at: string;
        }>;
      };
    },
  });

  return (
    <Box>
      <PageHeader
        title="Immutable Research Audit Logs"
        subtitle="Append-only regulatory & clinical research audit trail recording user authentication, patient edits, landmark adjustments, calibrations, and sign-offs"
        actions={
          <>
            <TextField
              size="small"
              label="Filter by Action Type"
              placeholder="e.g. LANDMARK_ADJUST"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              sx={{ backgroundColor: '#FFF' }}
            />
            <TextField
              size="small"
              label="Filter by Entity Type"
              placeholder="e.g. LandmarkPrediction"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              sx={{ backgroundColor: '#FFF' }}
            />
          </>
        }
      />

      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>Immutability Guarantee:</strong> Audit log records are protected by database-level{' '}
        <code>before_update</code> and <code>before_delete</code> listeners that reject any modification or deletion attempts.
      </Alert>

      {auditQuery.isLoading ? (
        <LoadingSkeleton rows={7} />
      ) : auditQuery.isError ? (
        <ErrorState message={extractErrorMessage(auditQuery.error)} onRetry={() => auditQuery.refetch()} />
      ) : (
        <Card>
          <CardContent sx={{ p: 0 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp (UTC)</TableCell>
                    <TableCell>Actor / User</TableCell>
                    <TableCell>Action Type</TableCell>
                    <TableCell>Entity Type & ID</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell align="right">State Diff</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(auditQuery.data?.items || []).map((log) => (
                    <TableRow key={log.id} hover>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                        {new Date(log.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{log.user_email}</TableCell>
                      <TableCell>
                        <Chip size="small" label={log.action_type} sx={{ fontWeight: 700, fontSize: '0.7rem' }} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {log.entity_type}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                          {log.entity_id || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>{log.description}</TableCell>
                      <TableCell align="right">
                        <Button size="small" variant="outlined" onClick={() => setSelectedAudit(log)}>
                          Before / After JSON
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      <Dialog open={Boolean(selectedAudit)} onClose={() => setSelectedAudit(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Audit Record State Diff — {selectedAudit?.action_type}
        </DialogTitle>
        <DialogContent dividers>
          {selectedAudit && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Before State (`before_json`)
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 1.5,
                    borderRadius: 1.5,
                    backgroundColor: '#0F172A',
                    color: '#E2E8F0',
                    fontSize: '0.75rem',
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(selectedAudit.before_json, null, 2)}
                </Box>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  After State (`after_json`)
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 1.5,
                    borderRadius: 1.5,
                    backgroundColor: '#0F172A',
                    color: '#5EEAD4',
                    fontSize: '0.75rem',
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(selectedAudit.after_json, null, 2)}
                </Box>
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedAudit(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 20: Study Protocol Configuration Screen
// ============================================================================
export const ProtocolConfigPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<number>(0);
  const [publishOpen, setPublishOpen] = useState<boolean>(false);
  const [newVersion, setNewVersion] = useState<string>('1.1');
  const [newTitle, setNewTitle] = useState<string>(
    'Longitudinal Quantitative Facial Asymmetry Study in Unilateral Mandibular Fractures (v1.1)'
  );
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const protocolQuery = useQuery({
    queryKey: ['admin-protocols'],
    queryFn: async () => {
      const res = await api.get('/admin/protocols');
      return res.data.data as {
        protocols: Array<{
          id: string;
          protocol_code: string;
          version: string;
          title: string;
          description: string;
          is_active: boolean;
          visit_schedule: Array<Record<string, any>>;
          required_image_views: string[];
          calibration_rules: Record<string, any>;
          review_rules: Record<string, any>;
        }>;
        landmark_definitions: Array<{
          id: string;
          code: string;
          name: string;
          side: string;
          anatomical_region: string;
          landmark_type: string;
          description: string;
        }>;
        measurement_definitions: Array<{
          id: string;
          code: string;
          name: string;
          measurement_type: string;
          unit: string;
          source_view: string;
          formula: string;
          description: string;
        }>;
      };
    },
  });

  const publishMut = useMutation({
    mutationFn: async () => {
      const res = await api.post('/admin/protocols', {
        version: newVersion,
        title: newTitle,
      });
      return res.data.data;
    },
    onSuccess: (p) => {
      setPublishOpen(false);
      setMsg({
        type: 'success',
        text: `Published and activated protocol ${p.protocol_code} version ${p.version}. Historical measurements remain linked to their original protocol version.`,
      });
      queryClient.invalidateQueries({ queryKey: ['admin-protocols'] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const activeProtocol =
    (protocolQuery.data?.protocols || []).find((p) => p.is_active) ||
    protocolQuery.data?.protocols?.[0];

  return (
    <Box>
      <PageHeader
        title="Study Protocol Configuration & Versioned Definitions"
        subtitle="Manage longitudinal visit schedules, anatomical & OPG landmark catalog, bilateral measurement formulas, and physical calibration rules"
        actions={
          <Button
            variant="contained"
            color="secondary"
            startIcon={<PublishIcon />}
            onClick={() => setPublishOpen(true)}
          >
            Publish New Protocol Version
          </Button>
        }
      />

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      {protocolQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : protocolQuery.isError ? (
        <ErrorState message={extractErrorMessage(protocolQuery.error)} onRetry={() => protocolQuery.refetch()} />
      ) : (
        <Stack spacing={2.5}>
          {activeProtocol && (
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap">
                  <Box>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography variant="h6" sx={{ fontWeight: 700, color: '#123B50' }}>
                        {activeProtocol.protocol_code} — {activeProtocol.title}
                      </Typography>
                      <Chip size="small" color="secondary" label={`Active v${activeProtocol.version}`} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {activeProtocol.description}
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          )}

          <Card>
            <Box sx={{ borderBottom: '1px solid #E2E8F0', px: 2 }}>
              <Tabs value={tab} onChange={(_, v) => setTab(v)}>
                <Tab label="5-Visit Longitudinal Schedule" />
                <Tab label={`Anatomical & OPG Landmarks (${protocolQuery.data?.landmark_definitions.length || 0})`} />
                <Tab label={`Validated Measurements (${protocolQuery.data?.measurement_definitions.length || 0})`} />
                <Tab label="Calibration & Review Rules" />
              </Tabs>
            </Box>

            <CardContent>
              {tab === 0 && activeProtocol && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Order</TableCell>
                        <TableCell>Visit Code</TableCell>
                        <TableCell>Clinical Stage Label</TableCell>
                        <TableCell>Target Day Offset</TableCell>
                        <TableCell>Allowed Window (Days)</TableCell>
                        <TableCell>Required Views</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {activeProtocol.visit_schedule.map((vs: any, idx: number) => (
                        <TableRow key={vs.visit_type}>
                          <TableCell>#{idx + 1}</TableCell>
                          <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{vs.visit_type}</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>{vs.label}</TableCell>
                          <TableCell>{vs.day_offset} days</TableCell>
                          <TableCell>±{vs.window_days} days</TableCell>
                          <TableCell>{activeProtocol.required_image_views.join(', ')}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab === 1 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Code</TableCell>
                        <TableCell>Landmark Name</TableCell>
                        <TableCell>Modality</TableCell>
                        <TableCell>Side</TableCell>
                        <TableCell>Anatomical Region</TableCell>
                        <TableCell>Clinical Definition</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(protocolQuery.data?.landmark_definitions || []).map((lm) => (
                        <TableRow key={lm.id}>
                          <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{lm.code}</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>{lm.name}</TableCell>
                          <TableCell>
                            <Chip size="small" label={lm.landmark_type} />
                          </TableCell>
                          <TableCell>{lm.side}</TableCell>
                          <TableCell>{lm.anatomical_region}</TableCell>
                          <TableCell>{lm.description}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab === 2 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Code</TableCell>
                        <TableCell>Measurement Name</TableCell>
                        <TableCell>Type & Unit</TableCell>
                        <TableCell>Source View</TableCell>
                        <TableCell>Mathematical Formula</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(protocolQuery.data?.measurement_definitions || []).map((m) => (
                        <TableRow key={m.id}>
                          <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{m.code}</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>{m.name}</TableCell>
                          <TableCell>
                            {m.measurement_type} ({m.unit})
                          </TableCell>
                          <TableCell>{m.source_view}</TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{m.formula}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab === 3 && activeProtocol && (
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, md: 6 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Physical Calibration Enforcement Rules
                    </Typography>
                    <Box
                      component="pre"
                      sx={{
                        p: 2,
                        borderRadius: 1.5,
                        backgroundColor: '#0F172A',
                        color: '#E2E8F0',
                        fontSize: '0.78rem',
                        overflowX: 'auto',
                      }}
                    >
                      {JSON.stringify(activeProtocol.calibration_rules, null, 2)}
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 12, md: 6 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Examiner Review & Sign-Off Rules
                    </Typography>
                    <Box
                      component="pre"
                      sx={{
                        p: 2,
                        borderRadius: 1.5,
                        backgroundColor: '#0F172A',
                        color: '#E2E8F0',
                        fontSize: '0.78rem',
                        overflowX: 'auto',
                      }}
                    >
                      {JSON.stringify(activeProtocol.review_rules, null, 2)}
                    </Box>
                  </Grid>
                </Grid>
              )}
            </CardContent>
          </Card>
        </Stack>
      )}

      <Dialog open={publishOpen} onClose={() => setPublishOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Publish New Protocol Version</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <TextField
              label="New Version Tag"
              size="small"
              fullWidth
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
            />
            <TextField
              label="Protocol Title"
              size="small"
              fullWidth
              multiline
              rows={2}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPublishOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => publishMut.mutate()} disabled={publishMut.isPending}>
            Publish Version
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// Settings & Security Page
// ============================================================================
export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [editSetting, setEditSetting] = useState<{
    key: string;
    value: string;
    description: string;
    is_secret: boolean;
    category: string;
  } | null>(null);

  const canManage = Boolean(user?.is_superuser || user?.permissions?.includes('config:manage'));

  const settingsQuery = useQuery({
    queryKey: ['admin-system-settings'],
    queryFn: async () => {
      const res = await api.get('/admin/settings');
      return res.data.data as {
        settings: Array<{
          id: string;
          key: string;
          value: string;
          is_configured: boolean;
          category: string;
          description: string;
          is_secret: boolean;
          is_editable: boolean;
          updated_at: string | null;
        }>;
        governance: Record<string, any>;
      };
    },
  });

  const changePwdMut = useMutation({
    mutationFn: async () => {
      const res = await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      return res.data.data;
    },
    onSuccess: (res) => {
      setMsg({ type: 'success', text: res.message || 'Password updated.' });
      setCurrentPassword('');
      setNewPassword('');
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const updateSettingMut = useMutation({
    mutationFn: async (payload: { key: string; value: string }) => {
      const res = await api.put(`/admin/settings/${payload.key}`, { value: payload.value });
      return res.data.data;
    },
    onSuccess: (data) => {
      setMsg({ type: 'success', text: `Setting '${data.key}' updated in database successfully.` });
      setEditSetting(null);
      queryClient.invalidateQueries({ queryKey: ['admin-system-settings'] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const dbSettings = settingsQuery.data?.settings || [];
  const governance = settingsQuery.data?.governance || {};

  return (
    <Box>
      <ResearchDisclaimerBanner />
      <PageHeader
        title="Platform Settings, Dynamic Credentials & Account Security"
        subtitle="Manage database-backed API keys, AI model credentials, storage parameters, and researcher security"
      />

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      <Stack spacing={2.5}>
        {/* PLATFORM USER MANUAL & INSTRUCTION GUIDE CARD */}
        <Card sx={{ border: '1px solid', borderColor: 'primary.main', bgcolor: 'background.paper', boxShadow: 1 }}>
          <CardContent>
            <Stack
              direction={{ xs: 'column', md: 'row' }}
              justifyContent="space-between"
              alignItems={{ xs: 'flex-start', md: 'center' }}
              spacing={2}
            >
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: 1.5,
                    bgcolor: 'primary.50',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'primary.main',
                    border: '1px solid',
                    borderColor: 'primary.light',
                  }}
                >
                  <MenuBookOutlinedIcon />
                </Box>
                <Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    Platform User Manual & Operating Instructions
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Official operating manual covering patient enrollment, 4 multi-modal views, 11-stage AI pipeline, physical scale calibration, and data governance.
                  </Typography>
                </Box>
              </Stack>
              <Stack direction="row" spacing={1.5}>
                <Button
                  variant="contained"
                  startIcon={<MenuBookOutlinedIcon fontSize="small" />}
                  onClick={() => navigate('/admin/instructions')}
                >
                  Open User Guide
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<DownloadOutlinedIcon fontSize="small" />}
                  component="a"
                  href="/api/v1/admin/instructions/download"
                  target="_blank"
                >
                  Download .MD
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        {/* TOP SECTION: Database-Backed System Settings & API Keys */}
        <Card>
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <VpnKeyOutlinedIcon color="primary" />
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Database-Backed Configuration & API Credentials
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              These settings are stored dynamically in the <code>system_settings</code> database table. You can configure
              your Gemini API key, storage engine, and AI parameters live here without modifying the <code>.env</code> file
              or restarting the server.
            </Typography>

            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Configuration Key</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Current Configured Value</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Status</TableCell>
                    {canManage && <TableCell align="right">Actions</TableCell>}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {dbSettings.map((s) => (
                    <TableRow key={s.key} hover>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                          {s.key}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip size="small" variant="outlined" label={s.category} />
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          sx={{
                            fontFamily: 'monospace',
                            color: s.is_configured ? 'text.primary' : 'text.secondary',
                            fontStyle: s.is_configured ? 'normal' : 'italic',
                          }}
                        >
                          {s.is_configured ? s.value : '(not set)'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {s.description}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          color={s.is_configured ? 'success' : 'default'}
                          label={s.is_configured ? 'Configured' : 'Unset'}
                        />
                      </TableCell>
                      {canManage && (
                        <TableCell align="right">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<EditOutlinedIcon fontSize="small" />}
                            onClick={() =>
                              setEditSetting({
                                key: s.key,
                                value: '',
                                description: s.description,
                                is_secret: s.is_secret,
                                category: s.category,
                              })
                            }
                          >
                            Edit
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>

        {/* BOTTOM SECTION: User Profile & Governance Metadata */}
        <Grid container spacing={2.5}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                  <SecurityIcon color="primary" />
                  <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    Current User Profile & Session
                  </Typography>
                </Stack>
                <Stack spacing={1}>
                  <Typography variant="body2">
                    <strong>Full Name:</strong> {user?.full_name}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Email:</strong> {user?.email}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Primary Role:</strong> {user?.primary_role}
                  </Typography>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    Change Researcher Password
                  </Typography>
                  <TextField
                    label="Current Password"
                    type="password"
                    size="small"
                    fullWidth
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                  />
                  <TextField
                    label="New Password (min 8 chars)"
                    type="password"
                    size="small"
                    fullWidth
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                  <Button
                    variant="contained"
                    disabled={!currentPassword || newPassword.length < 8 || changePwdMut.isPending}
                    onClick={() => changePwdMut.mutate()}
                  >
                    Update Password
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                  System Governance & Research Integrity Configuration
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 2,
                    borderRadius: 1.5,
                    backgroundColor: '#0F172A',
                    color: '#E2E8F0',
                    fontSize: '0.78rem',
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(governance, null, 2)}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Stack>

      {/* Edit Setting Dialog */}
      <Dialog open={Boolean(editSetting)} onClose={() => setEditSetting(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Configure System Setting — {editSetting?.key}
        </DialogTitle>
        <DialogContent dividers>
          {editSetting && (
            <Stack spacing={2} sx={{ mt: 0.5 }}>
              <Alert severity="info" sx={{ fontSize: '0.8rem' }}>
                {editSetting.description}
              </Alert>
              <TextField
                label={editSetting.is_secret ? 'Enter New API Key / Secret' : 'Setting Value'}
                type={editSetting.is_secret ? 'password' : 'text'}
                size="small"
                fullWidth
                required
                value={editSetting.value}
                onChange={(e) => setEditSetting({ ...editSetting, value: e.target.value })}
                helperText={
                  editSetting.is_secret
                    ? 'Enter the new secret (e.g. AIzaSy...). Value will be saved in the database and masked.'
                    : 'Changes take effect immediately across all active AI pipelines.'
                }
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditSetting(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!editSetting || !editSetting.value.trim() || updateSettingMut.isPending}
            onClick={() => {
              if (editSetting) {
                updateSettingMut.mutate({
                  key: editSetting.key,
                  value: editSetting.value.trim(),
                });
              }
            }}
          >
            Save to Database
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// Platform User Manual & Operating Instructions Page
// ============================================================================
export const PlatformInstructionsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);

  const instructionsQuery = useQuery({
    queryKey: ['platform-instructions'],
    queryFn: async () => {
      const res = await api.get('/admin/instructions');
      return res.data.data as {
        filename: string;
        title: string;
        content: string;
        sections: string[];
        size_bytes: number;
        last_modified: string;
      };
    },
  });

  const content = instructionsQuery.data?.content || '';
  const sections = instructionsQuery.data?.sections || [];

  const handleCopy = () => {
    if (content) {
      navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <Box sx={{ pb: 6 }}>
      <ResearchDisclaimerBanner />
      
      {/* HEADER & ACTION CONTROLS */}
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
        spacing={2}
        sx={{ mb: 2.5 }}
      >
        <Box>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <MenuBookOutlinedIcon color="primary" sx={{ fontSize: 32 }} />
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              Platform User Manual & Operating Instructions
            </Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Standard operating procedures, 11-stage AI pipeline workflows, RBAC privileges, and calibration standards
          </Typography>
        </Box>

        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Button
            variant="outlined"
            size="small"
            startIcon={<ContentCopyOutlinedIcon fontSize="small" />}
            onClick={handleCopy}
            color={copied ? 'success' : 'inherit'}
          >
            {copied ? 'Copied Markdown!' : 'Copy Markdown'}
          </Button>

          <Button
            variant="outlined"
            size="small"
            startIcon={<PrintOutlinedIcon fontSize="small" />}
            onClick={handlePrint}
            color="inherit"
          >
            Print / PDF
          </Button>

          <Button
            variant="contained"
            size="small"
            startIcon={<DownloadOutlinedIcon fontSize="small" />}
            component="a"
            href="/api/v1/admin/instructions/download"
            target="_blank"
            download="AI_Facial_Asymmetry_Analysis_Platform_User_Manual.md"
          >
            Download Guide (.md)
          </Button>
        </Stack>
      </Stack>

      {/* METADATA BAR */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3, borderRadius: 2, bgcolor: 'background.paper' }}>
        <Grid container spacing={2} alignItems="center">
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              Study Target Population
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              Unilateral Mandibular Fractures
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2.5 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              Longitudinal Visits
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              5 Standard Protocol Milestones
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2.5 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              Multi-Modal Acquisition
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              4 Standardized Views / Visit
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              AI Analysis Engine
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              11 Automated Stages
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              Source Documentation
            </Typography>
            <Chip size="small" variant="outlined" label={instructionsQuery.data?.filename || 'docs/INSTRUCTIONS_HOW_TO_USE.md'} />
          </Grid>
        </Grid>
      </Paper>

      {/* TABS & SEARCH */}
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="center" spacing={2} sx={{ mb: 2.5 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)}>
          <Tab label="Interactive User Guide" icon={<MenuBookOutlinedIcon fontSize="small" />} iconPosition="start" />
          <Tab label="Raw Markdown Source" icon={<DescriptionOutlinedIcon fontSize="small" />} iconPosition="start" />
        </Tabs>

        {activeTab === 0 && (
          <TextField
            size="small"
            placeholder="Search instructions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchOutlinedIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
            sx={{ width: { xs: '100%', sm: 280 } }}
          />
        )}
      </Stack>

      {/* TAB 0: INTERACTIVE USER GUIDE */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {/* Quick TOC Sidebar */}
          <Grid size={{ xs: 12, md: 3.5 }}>
            <Card sx={{ position: { md: 'sticky' }, top: 84 }}>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 1.5, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Manual Chapters
                </Typography>
                <Stack spacing={0.75}>
                  {[
                    { id: 'section-1', title: '1. Platform Overview & Scope' },
                    { id: 'section-2', title: '2. User Roles & RBAC Matrix' },
                    { id: 'section-3', title: '3. Longitudinal Protocol' },
                    { id: 'section-4', title: '4. Step-by-Step Workflow' },
                    { id: 'section-5', title: '5. Dynamic System Settings' },
                    { id: 'section-6', title: '6. Troubleshooting & FAQ' },
                  ].map((ch) => (
                    <Button
                      key={ch.id}
                      size="small"
                      variant="text"
                      color="inherit"
                      sx={{
                        justifyContent: 'flex-start',
                        textAlign: 'left',
                        fontWeight: 600,
                        fontSize: '0.82rem',
                        py: 0.5,
                        px: 1,
                        borderRadius: 1,
                        '&:hover': { bgcolor: 'action.hover', color: 'primary.main' },
                      }}
                      onClick={() => {
                        const el = document.getElementById(ch.id);
                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }}
                    >
                      {ch.title}
                    </Button>
                  ))}
                </Stack>

                <Divider sx={{ my: 2 }} />

                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  Quick Jump References:
                </Typography>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  {['MediaPipe', 'OPG Calibration', 'Gemini AI', 'Dijkstra 3D', 'Bland-Altman', 'run.bat'].map((tag) => (
                    <Chip
                      key={tag}
                      size="small"
                      label={tag}
                      clickable
                      onClick={() => setSearchQuery(tag)}
                      sx={{ fontSize: '0.72rem' }}
                    />
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          {/* Guide Content Sections */}
          <Grid size={{ xs: 12, md: 8.5 }}>
            <Stack spacing={3}>
              {/* SECTION 1: OVERVIEW */}
              <Card id="section-1">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    1. Platform Overview & Clinical Scope
                  </Typography>
                  <Typography variant="body2" sx={{ lineHeight: 1.7, mb: 2 }}>
                    The <strong>AI Facial Asymmetry Analysis Platform</strong> is an enterprise clinical research system designed to standardize, accelerate, and validate quantitative facial asymmetry assessments in patients who have sustained <strong>unilateral mandibular fractures treated by open or closed reduction and internal fixation (ORIF)</strong>.
                  </Typography>

                  <Alert severity="warning" sx={{ mb: 2 }}>
                    <strong>Clinical Research Notice:</strong> This software is strictly intended for research measurement, documentation, and biostatistical tracking. Outputs do not constitute a medical diagnosis or treatment directive. All measurements require clinical examiner sign-off.
                  </Alert>

                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 4 }}>
                      <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main' }}>
                          Dual-Coordinate Audit
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          AI raw predictions (predicted_x/y) are permanently preserved alongside examiner adjustments (examiner_x/y).
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                      <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'secondary.main' }}>
                          Physical Scale Rigor
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Rejects generic screen PPI (1 mm ≠ 3.78 px). Requires 2-point fiducial ruler or OPG magnification scaling.
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                      <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'success.main' }}>
                          Biostatistical Validity
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Computes Asymmetry Index (%), Intraclass Correlation ICC(2,1), Bland–Altman bias, and longitudinal recovery deltas.
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>

              {/* SECTION 2: ROLES & RBAC */}
              <Card id="section-2">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    2. User Roles & Access Permissions (RBAC)
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    The platform enforces strict role-based access control. All seeded development accounts share the password: <code>Research@2026</code>.
                  </Typography>

                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Role</TableCell>
                          <TableCell>Default Seed Email</TableCell>
                          <TableCell>Permitted Operations & Modules</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {[
                          { role: 'System Administrator', email: 'admin@faplatform.org', perms: 'Full governance, dynamic API keys, system audit logs, storage' },
                          { role: 'Principal Investigator', email: 'pi@faplatform.org', perms: 'Study protocol, visit sign-offs, clinical telemetry, audit review' },
                          { role: 'Research Coordinator', email: 'coordinator@faplatform.org', perms: 'Patient recruitment, demographics, visit scheduling, image upload' },
                          { role: 'Clinician / Examiner', email: 'examiner@faplatform.org', perms: 'Landmark refinement, scale calibration, measurement approvals' },
                          { role: 'Research Analyst', email: 'analyst@faplatform.org', perms: 'Anonymized queries, ICC / Bland-Altman modeling, data exports' },
                          { role: 'Read-only Researcher', email: 'readonly@faplatform.org', perms: 'De-identified longitudinal viewing and report downloads' },
                        ].map((r) => (
                          <TableRow key={r.role} hover>
                            <TableCell>
                              <Chip size="small" label={r.role} color="primary" variant="outlined" />
                            </TableCell>
                            <TableCell>
                              <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                                {r.email}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="caption" color="text.secondary">
                                {r.perms}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>

              {/* SECTION 3: PROTOCOL MILESTONES */}
              <Card id="section-3">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    3. Longitudinal Protocol & Study Milestones
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    Every subject is evaluated across 5 mandatory longitudinal milestones to measure anatomical and soft tissue symmetry recovery:
                  </Typography>

                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between">
                    {[
                      { step: '1', title: 'PreOperative', sub: 'Baseline deformity' },
                      { step: '2', title: 'PostOp 1 Wk', sub: 'Early edema baseline' },
                      { step: '3', title: 'PostOp 6 Wks', sub: 'Primary bony union' },
                      { step: '4', title: 'PostOp 3 Mo', sub: 'Remodeling phase' },
                      { step: '5', title: 'PostOp 6 Mo', sub: 'Final stable outcome' },
                    ].map((m) => (
                      <Paper
                        key={m.title}
                        variant="outlined"
                        sx={{
                          p: 1.5,
                          flex: 1,
                          textAlign: 'center',
                          bgcolor: 'background.default',
                          borderTop: '3px solid',
                          borderColor: 'primary.main',
                        }}
                      >
                        <Typography variant="caption" color="primary.main" sx={{ fontWeight: 800 }}>
                          VISIT {m.step}
                        </Typography>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          {m.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {m.sub}
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                </CardContent>
              </Card>

              {/* SECTION 4: STEP-BY-STEP WORKFLOW */}
              <Card id="section-4">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    4. Step-by-Step Clinical Research Workflow
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
                    Follow this sequential operational procedure for every study visit:
                  </Typography>

                  <Stack spacing={2}>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.1: Patient Enrollment
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        Go to <strong>Patients</strong> &rarr; <strong>New Patient</strong>. Record de-identified study ID (e.g. <code>FA-2026-001</code>), fracture anatomical zone (Condyle, Angle, Body, Symphysis, Ramus), and surgical fixation technique (e.g. ORIF with miniplates).
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.2: Schedule Study Visit & Upload 4 Multi-Modal Views
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem', mb: 1 }}>
                        Create a study visit milestone and upload the four standardized views required for cross-validation:
                      </Typography>
                      <Grid container spacing={1}>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Chip size="small" label="1. Frontal Photo" variant="outlined" sx={{ width: '100%' }} />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Chip size="small" label="2. Right Lateral" variant="outlined" sx={{ width: '100%' }} />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Chip size="small" label="3. Left Lateral" variant="outlined" sx={{ width: '100%' }} />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Chip size="small" label="4. Panoramic OPG" variant="outlined" sx={{ width: '100%' }} />
                        </Grid>
                      </Grid>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.3: Execute 11-Stage AI Pipeline
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        Click <strong>Run AI Analysis Pipeline</strong>. The automated engine performs landmark extraction (MediaPipe 478 points), anatomical segmentation, quality checks, 3D surface mesh reconstruction, Dijkstra geodesic path compute, and automated draft report generation.
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.4: Physical Scale Calibration (Fiducial Ruler & OPG Magnification)
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        In the <strong>Scale Calibration</strong> tab, calibrate image pixels to real millimeters:
                        <br />
                        &bull; <strong>Photos</strong>: Select 2 points on the circular or linear ruler marker and enter physical length in mm (<code>Scale = known_mm / measured_px</code>).
                        <br />
                        &bull; <strong>OPG Radiograph</strong>: Enter the panoramic device magnification factor (typically <code>1.25x</code>).
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.5: Interactive SVG/Canvas Landmark Review & Examiner Refinement
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        In the <strong>Landmarks</strong> tab, zoom (up to 400%) and drag any predicted point (Gonion, Cheilion, Exocanthion, Menton) to anatomical boundaries. The system retains original AI predictions alongside your adjustments in the audit ledger.
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main', mb: 0.5 }}>
                        Step 4.6: Review Asymmetry Indices & Export Multi-Format Reports
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        Review bilateral differences: Absolute Delta |R - L| (in mm) and Asymmetry Index AI % = (|R - L| / (R + L)) * 100%. Export publication-ready comprehensive PDF dossiers, CSV measurement sheets, Excel workbooks, or 3D OBJ/PLY meshes.
                      </Typography>
                    </Paper>
                  </Stack>
                </CardContent>
              </Card>

              {/* SECTION 5: DYNAMIC SETTINGS */}
              <Card id="section-5">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    5. System Administration & Database-Backed Settings
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    Administrators can manage API credentials and system parameters dynamically from the <strong>Administration</strong> &rarr; <strong>Settings</strong> page without restarting Docker or modifying <code>.env</code> files:
                  </Typography>

                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Key</TableCell>
                          <TableCell>Purpose & Target Engine</TableCell>
                          <TableCell>Default</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {[
                          { key: 'GEMINI_API_KEY', desc: 'Google Gemini 2.0/2.5 for AI narrative reports', def: '(stored in DB table)' },
                          { key: 'NVIDIA_API_KEY', desc: 'NVIDIA NIM API key for hardware-accelerated models', def: '(stored in DB table)' },
                          { key: 'OPENAI_API_KEY', desc: 'OpenAI GPT-4o for multimodal report validation', def: '(stored in DB table)' },
                          { key: 'STORAGE_BACKEND', desc: 'Blob engine: database, local, or s3', def: 'database' },
                          { key: 'TASK_BACKEND', desc: 'Async queue engine: inline or celery', def: 'inline' },
                          { key: 'ALLOW_EXTERNAL_AI_UPLOADS', desc: 'Toggle cloud AI API calls vs air-gapped local', def: 'false' },
                        ].map((s) => (
                          <TableRow key={s.key} hover>
                            <TableCell>
                              <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                                {s.key}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="caption" color="text.secondary">
                                {s.desc}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Chip size="small" variant="outlined" label={s.def} />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>

              {/* SECTION 6: FAQ */}
              <Card id="section-6">
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1, color: 'primary.main' }}>
                    6. Single-Shot Execution & Troubleshooting FAQ
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Frequently asked technical questions regarding Windows and Docker execution:
                  </Typography>

                  <Stack spacing={1.5}>
                    <Accordion defaultExpanded>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          How does the single-shot run.bat script work?
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                          Double-clicking <code>run.bat</code> automatically verifies Docker, starts Docker Desktop if stopped, updates code from Git (<code>git pull</code>), reuses existing PostgreSQL (<code>fa_postgres</code>) and Redis (<code>fa_redis</code>) containers without recreating them, rebuilds backend and frontend with updated files, and opens your browser to <code>http://localhost:5173</code>.
                        </Typography>
                      </AccordionDetails>
                    </Accordion>

                    <Accordion>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          Why do my measurements say "Unscaled"?
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                          Measurements require physical calibration before they can be reported in millimeters. Open the visit, go to the <strong>Scale Calibration</strong> tab, select two points on your visible ruler fiducial, and enter its known length in millimeters.
                        </Typography>
                      </AccordionDetails>
                    </Accordion>

                    <Accordion>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          Can I use the platform completely offline?
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                          Yes! The platform includes pre-downloaded Google MediaPipe 478-point neural models (<code>backend/models/mediapipe/</code>). In System Settings, set <code>ALLOW_EXTERNAL_AI_UPLOADS=false</code> to ensure no data ever leaves your local network.
                        </Typography>
                      </AccordionDetails>
                    </Accordion>

                    <Accordion>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          Where are the interactive Swagger API docs?
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                          When running, visit <code>http://localhost:5173/docs</code> or <code>http://localhost:8000/docs</code> to inspect and execute all 40+ REST API endpoints interactively.
                        </Typography>
                      </AccordionDetails>
                    </Accordion>
                  </Stack>
                </CardContent>
              </Card>
            </Stack>
          </Grid>
        </Grid>
      )}

      {/* TAB 1: RAW MARKDOWN SOURCE */}
      {activeTab === 1 && (
        <Card>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Raw Markdown Source ({instructionsQuery.data?.filename || 'INSTRUCTIONS_HOW_TO_USE.md'})
              </Typography>
              <Button
                size="small"
                variant="outlined"
                startIcon={<ContentCopyOutlinedIcon fontSize="small" />}
                onClick={handleCopy}
              >
                {copied ? 'Copied!' : 'Copy Raw Text'}
              </Button>
            </Stack>
            <Box
              component="pre"
              sx={{
                p: 2.5,
                borderRadius: 1.5,
                backgroundColor: '#0F172A',
                color: '#E2E8F0',
                fontSize: '0.82rem',
                lineHeight: 1.6,
                fontFamily: 'monospace',
                overflowX: 'auto',
                maxHeight: '70vh',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {content || 'Loading instruction manual...'}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};
