import React, { useState } from 'react';
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import DownloadIcon from '@mui/icons-material/Download';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import VisibilityIcon from '@mui/icons-material/Visibility';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage, withAuthTokenUrl } from '@/services/api';
import {
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingSkeleton,
  PageHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { PatientSummary } from '@/types';

// ============================================================================
// PAGE 16: Report Generation and Export Center
// ============================================================================
export const ReportsCenterPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [reportTitle, setReportTitle] = useState<string>('');
  const [reportType, setReportType] = useState<string>('LongitudinalResearchReport');
  const [previewReport, setPreviewReport] = useState<Record<string, any> | null>(null);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const patientsQuery = useQuery({
    queryKey: ['patients-for-reports'],
    queryFn: async () => {
      const res = await api.get('/patients?page=1&page_size=50');
      const d = res.data.data;
      return (Array.isArray(d) ? d : d?.items || []) as PatientSummary[];
    },
  });

  const reportsQuery = useQuery({
    queryKey: ['reports-list'],
    queryFn: async () => {
      const res = await api.get('/reports');
      return res.data.data as Array<{
        id: string;
        patient_id: string;
        patient_code: string;
        visit_id: string | null;
        report_code: string;
        title: string;
        report_type: string;
        status: string;
        ai_provider: string;
        model_version: string;
        summary_text: string;
        content_json: Record<string, any>;
        created_at: string;
        downloads: {
          pdf: string;
          csv: string;
          xlsx: string;
          json: string;
          obj: string;
          ply: string;
        };
      }>;
    },
  });

  const generateMut = useMutation({
    mutationFn: async () => {
      const pid = selectedPatientId || patientsQuery.data?.[0]?.id;
      if (!pid) throw new Error('Select a patient first');
      const res = await api.post('/reports/generate', {
        patient_id: pid,
        report_type: reportType,
        title: reportTitle || undefined,
      });
      return res.data.data;
    },
    onSuccess: (rep) => {
      setMsg({
        type: 'success',
        text: `Generated 13-section research report ${rep.report_code} (${rep.title}) with PDF, CSV, Excel, JSON, OBJ, and PLY exports.`,
      });
      setPreviewReport(rep);
      queryClient.invalidateQueries({ queryKey: ['reports-list'] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  return (
    <Box>
      <ResearchDisclaimerBanner />

      <PageHeader
        title="Report Generation & Research Export Center"
        subtitle="Generate 13-section clinical research reports and export validated measurements & 3D meshes in PDF, CSV, Excel, JSON, OBJ, and PLY formats"
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              component="a"
              href={withAuthTokenUrl('/api/v1/reports/cohort/export?format=csv')}
              target="_blank"
            >
              Cohort Dataset (CSV)
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              component="a"
              href={withAuthTokenUrl('/api/v1/reports/cohort/export?format=xlsx')}
              target="_blank"
            >
              Cohort Dataset (Excel)
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              component="a"
              href={withAuthTokenUrl('/api/v1/reports/cohort/export?format=json')}
              target="_blank"
            >
              Cohort Dataset (JSON)
            </Button>
          </>
        }
      />

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      {/* Report Generator Card */}
      <Card sx={{ mb: 2.5 }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
            Generate New 13-Section Patient Research Report
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Select Study Patient</InputLabel>
                <Select
                  label="Select Study Patient"
                  value={selectedPatientId || patientsQuery.data?.[0]?.id || ''}
                  onChange={(e) => setSelectedPatientId(e.target.value)}
                >
                  {(patientsQuery.data || []).map((p) => (
                    <MenuItem key={p.id} value={p.id}>
                      {p.patient_code} — {p.fracture_side} {p.fracture_type} ({p.study_status})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>Report Scope</InputLabel>
                <Select
                  label="Report Scope"
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value)}
                >
                  <MenuItem value="LongitudinalResearchReport">Longitudinal Multi-Visit Report</MenuItem>
                  <MenuItem value="SingleVisitSummary">Single Visit Quantitative Report</MenuItem>
                  <MenuItem value="ExaminerSignOffDossier">Examiner Sign-Off Dossier</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                label="Custom Report Title (Optional)"
                size="small"
                fullWidth
                value={reportTitle}
                onChange={(e) => setReportTitle(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <Button
                fullWidth
                variant="contained"
                color="secondary"
                startIcon={<AddCircleOutlineIcon />}
                disabled={generateMut.isPending}
                onClick={() => generateMut.mutate()}
              >
                {generateMut.isPending ? 'Generating...' : 'Generate'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Generated Reports Table */}
      {reportsQuery.isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : reportsQuery.isError ? (
        <ErrorState message={extractErrorMessage(reportsQuery.error)} onRetry={() => reportsQuery.refetch()} />
      ) : !reportsQuery.data?.length ? (
        <EmptyState title="No research reports generated yet" />
      ) : (
        <Card>
          <CardContent sx={{ p: 0 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Report Code</TableCell>
                    <TableCell>Patient Code</TableCell>
                    <TableCell>Title & Type</TableCell>
                    <TableCell>AI / Template Engine</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Generated At</TableCell>
                    <TableCell align="right">Preview & Multi-Format Exports</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {reportsQuery.data.map((r) => (
                    <TableRow key={r.id} hover>
                      <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{r.report_code}</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>{r.patient_code}</TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {r.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {r.report_type}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip size="small" label={`${r.ai_provider} (${r.model_version})`} />
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={r.status} />
                      </TableCell>
                      <TableCell>{new Date(r.created_at).toLocaleString()}</TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={0.6} justifyContent="flex-end" flexWrap="wrap">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<VisibilityIcon fontSize="small" />}
                            onClick={() => setPreviewReport(r)}
                          >
                            13 Sections
                          </Button>
                          <Button
                            size="small"
                            variant="contained"
                            color="primary"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.pdf)}
                            target="_blank"
                          >
                            PDF
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.csv)}
                            target="_blank"
                          >
                            CSV
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.xlsx)}
                            target="_blank"
                          >
                            XLSX
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.json)}
                            target="_blank"
                          >
                            JSON
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.obj)}
                            target="_blank"
                          >
                            OBJ
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            component="a"
                            href={withAuthTokenUrl(r.downloads.ply)}
                            target="_blank"
                          >
                            PLY
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

      {/* 13-Section Report Preview Modal */}
      <Dialog open={Boolean(previewReport)} onClose={() => setPreviewReport(null)} maxWidth="lg" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Box>
              <DescriptionIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {previewReport?.report_code} — {previewReport?.title}
            </Box>
            {previewReport?.downloads && (
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="contained"
                  component="a"
                  href={withAuthTokenUrl(previewReport.downloads.pdf)}
                  target="_blank"
                >
                  Download PDF
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  component="a"
                  href={withAuthTokenUrl(previewReport.downloads.xlsx)}
                  target="_blank"
                >
                  Download Excel
                </Button>
              </Stack>
            )}
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          {previewReport && (
            <Stack spacing={2}>
              <Alert severity="info">
                <strong>Section 13 Research Disclaimer:</strong>{' '}
                {previewReport.content_json?.section_13_research_disclaimer}
              </Alert>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
                {previewReport.summary_text}
              </Typography>
              <Divider />
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Structured 13-Section Report Payload (Sections 1–13)
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
                  maxHeight: 420,
                }}
              >
                {JSON.stringify(previewReport.content_json, null, 2)}
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewReport(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ============================================================================
// PAGE 17: Research Analytics & Biostatistical Reliability Dashboard
// ============================================================================
export const ResearchAnalyticsPage: React.FC = () => {
  const [selectedMetric, setSelectedMetric] = useState<string>('BIGONIAL_BREADTH');
  const [fractureSideFilter, setFractureSideFilter] = useState<string>('');

  const analyticsQuery = useQuery({
    queryKey: ['research-analytics', selectedMetric, fractureSideFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ measurement_code: selectedMetric });
      if (fractureSideFilter) params.set('fracture_side', fractureSideFilter);
      const res = await api.get(`/analytics/overview?${params.toString()}`);
      return res.data.data as {
        selected_measurement_code: string;
        filters: { fracture_side: string | null };
        cohort_size: number;
        enrollment_trends: Array<{ month: string; count: number }>;
        follow_up_completion_rates: Array<{
          visit_type: string;
          label: string;
          completed: number;
          total: number;
          completion_rate_pct: number;
        }>;
        visit_wise_trends: Array<{
          visit_type: string;
          label: string;
          n: number;
          mean_asymmetry_index: number | null;
          sd_asymmetry_index: number | null;
          median_asymmetry_index: number | null;
        }>;
        measurement_distributions: Record<string, any>;
        histogram: Array<{ bin_label: string; count: number }>;
        missing_data_analysis: Array<{
          visit_type: string;
          label: string;
          total_expected: number;
          available_count: number;
          missing_count: number;
          missing_rate_pct: number;
        }>;
        reliability: {
          icc_2_1_ai_vs_examiner: {
            status: string;
            n: number;
            icc_2_1: number | null;
            ci_95_lower: number | null;
            ci_95_upper: number | null;
            f_value: number | null;
            reason?: string;
          };
          bland_altman_ai_vs_examiner: {
            status: string;
            n: number;
            mean_bias: number | null;
            sd_diff: number | null;
            loa_upper_95: number | null;
            loa_lower_95: number | null;
            points?: Array<{ mean: number; diff: number; a: number; b: number }>;
            reason?: string;
          };
          coefficient_of_variation: {
            status: string;
            n: number;
            mean: number | null;
            sd: number | null;
            cv_percent: number | null;
            reason?: string;
          };
        };
      };
    },
  });

  const data = analyticsQuery.data;
  const icc = data?.reliability?.icc_2_1_ai_vs_examiner;
  const ba = data?.reliability?.bland_altman_ai_vs_examiner;
  const cv = data?.reliability?.coefficient_of_variation;

  return (
    <Box>
      <ResearchDisclaimerBanner compact />

      <PageHeader
        title="Research Analytics & Biostatistical Validation Dashboard"
        subtitle="Cohort-level facial asymmetry distributions, longitudinal healing trajectories, missing-data audit, ICC(2,1), Bland–Altman limits of agreement, and CV%"
        actions={
          <>
            <FormControl size="small" sx={{ minWidth: 250, backgroundColor: '#FFF' }}>
              <InputLabel>Measurement Parameter</InputLabel>
              <Select
                label="Measurement Parameter"
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
              >
                <MenuItem value="BIGONIAL_BREADTH">BIGONIAL_BREADTH — Bigonial Facial Breadth</MenuItem>
                <MenuItem value="GONION_TO_MENTON">GONION_TO_MENTON — Mandibular Body Length</MenuItem>
                <MenuItem value="TRAGUS_TO_GONION">TRAGUS_TO_GONION — Posterior Ramal Height</MenuItem>
                <MenuItem value="GONIAL_ANGLE_PHOTO">GONIAL_ANGLE_PHOTO — Photographic Gonial Angle</MenuItem>
                <MenuItem value="OPG_RAMUS_HEIGHT">OPG_RAMUS_HEIGHT — OPG Condylion–Gonion</MenuItem>
                <MenuItem value="OPG_CORPUS_LENGTH">OPG_CORPUS_LENGTH — OPG Gonion–Menton</MenuItem>
                <MenuItem value="OPG_GONIAL_ANGLE">OPG_GONIAL_ANGLE — OPG Gonial Angle</MenuItem>
                <MenuItem value="GEODESIC_TRAGUS_POGONION">GEODESIC_TRAGUS_POGONION — 3D Geodesic Path</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 180, backgroundColor: '#FFF' }}>
              <InputLabel>Fracture Side Filter</InputLabel>
              <Select
                label="Fracture Side Filter"
                value={fractureSideFilter}
                onChange={(e) => setFractureSideFilter(e.target.value)}
              >
                <MenuItem value="">All Unilateral (R + L)</MenuItem>
                <MenuItem value="Right">Right Mandible Only</MenuItem>
                <MenuItem value="Left">Left Mandible Only</MenuItem>
              </Select>
            </FormControl>
          </>
        }
      />

      {analyticsQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : analyticsQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(analyticsQuery.error)}
          onRetry={() => analyticsQuery.refetch()}
        />
      ) : !data ? (
        <EmptyState title="No analytics data available" />
      ) : (
        <Stack spacing={2.5}>
          {/* Top Biostatistical Reliability KPI Strip */}
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiCard
                label="Cohort Sample Size"
                value={`${data.cohort_size} Patients`}
                subtitle={`Filter: ${fractureSideFilter || 'All Unilateral'}`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiCard
                label="ICC(2,1) AI vs Examiner"
                value={
                  icc?.status === 'Calculated' && icc.icc_2_1 != null
                    ? `${icc.icc_2_1.toFixed(4)} (n=${icc.n})`
                    : `Insufficient n (${icc?.n || 0})`
                }
                subtitle={
                  icc?.status === 'Calculated'
                    ? `95% CI [${icc.ci_95_lower?.toFixed(3)}, ${icc.ci_95_upper?.toFixed(3)}]`
                    : icc?.reason || 'Requires paired AI & examiner coordinates'
                }
                accent="#087E8B"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiCard
                label="Bland–Altman Mean Bias"
                value={
                  ba?.status === 'Calculated' && ba.mean_bias != null
                    ? `${ba.mean_bias.toFixed(3)} px (n=${ba.n})`
                    : `Insufficient n (${ba?.n || 0})`
                }
                subtitle={
                  ba?.status === 'Calculated'
                    ? `95% LoA [${ba.loa_lower_95?.toFixed(2)}, ${ba.loa_upper_95?.toFixed(2)}]`
                    : ba?.reason || 'Requires >= 3 paired observations'
                }
                accent="#2563EB"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiCard
                label="Coeff. of Variation (CV%)"
                value={
                  cv?.status === 'Calculated' && cv.cv_percent != null
                    ? `${cv.cv_percent.toFixed(2)} % (n=${cv.n})`
                    : 'Insufficient Data'
                }
                subtitle={
                  cv?.status === 'Calculated'
                    ? `Mean=${cv.mean?.toFixed(2)} %, SD=${cv.sd?.toFixed(2)} %`
                    : cv?.reason
                }
                accent="#16A34A"
              />
            </Grid>
          </Grid>

          {/* Row 1 Charts: Visit-wise Asymmetry Trend + Bland-Altman Plot */}
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 12, lg: 6 }}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Visit-Wise Cohort Asymmetry Index (%) Trajectory ({selectedMetric})
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                    Cohort Mean vs Median Asymmetry Index (%) across the 5 post-fixation study visits
                  </Typography>
                  <Box sx={{ width: '100%', height: 290 }}>
                    <ResponsiveContainer>
                      <LineChart data={data.visit_wise_trends}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RechartsTooltip />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="mean_asymmetry_index"
                          name="Mean Asymmetry Index (%)"
                          stroke="#123B50"
                          strokeWidth={3}
                          dot={{ r: 5 }}
                        />
                        <Line
                          type="monotone"
                          dataKey="median_asymmetry_index"
                          name="Median Asymmetry Index (%)"
                          stroke="#087E8B"
                          strokeWidth={2.5}
                          strokeDasharray="5 3"
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
                    Bland–Altman Agreement Plot (AI Prediction vs Examiner Coordinate)
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                    Difference (AI - Examiner) vs Mean with Mean Bias and ±1.96 SD Limits of Agreement
                  </Typography>
                  {ba?.status !== 'Calculated' || !ba.points?.length ? (
                    <Alert severity="warning">{ba?.reason || 'Insufficient paired observations'}</Alert>
                  ) : (
                    <Box sx={{ width: '100%', height: 290 }}>
                      <ResponsiveContainer>
                        <ScatterChart>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" dataKey="mean" name="Mean (px)" tick={{ fontSize: 11 }} />
                          <YAxis type="number" dataKey="diff" name="Diff (AI - Examiner)" tick={{ fontSize: 11 }} />
                          <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} />
                          {ba.mean_bias != null && (
                            <ReferenceLine y={ba.mean_bias} stroke="#087E8B" strokeWidth={2} />
                          )}
                          {ba.loa_upper_95 != null && (
                            <ReferenceLine y={ba.loa_upper_95} stroke="#EF4444" strokeDasharray="4 4" />
                          )}
                          {ba.loa_lower_95 != null && (
                            <ReferenceLine y={ba.loa_lower_95} stroke="#EF4444" strokeDasharray="4 4" />
                          )}
                          <Scatter name="Paired Landmarks" data={ba.points} fill="#123B50" />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Row 2 Charts: Measurement Histogram + Follow-Up Completion Rate */}
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 12, lg: 6 }}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                    Asymmetry Index (%) Distribution Histogram ({selectedMetric})
                  </Typography>
                  <Box sx={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer>
                      <BarChart data={data.histogram}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="bin_label" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RechartsTooltip />
                        <Bar dataKey="count" name="Visit Observations" fill="#087E8B" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, lg: 6 }}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                    Missing-Data Audit & Follow-Up Completeness by Study Stage
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Study Stage</TableCell>
                          <TableCell align="right">Expected</TableCell>
                          <TableCell align="right">Available (n)</TableCell>
                          <TableCell align="right">Missing (n)</TableCell>
                          <TableCell align="right">Missing Rate (%)</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.missing_data_analysis.map((row) => (
                          <TableRow key={row.visit_type}>
                            <TableCell sx={{ fontWeight: 700 }}>{row.label}</TableCell>
                            <TableCell align="right">{row.total_expected}</TableCell>
                            <TableCell align="right">{row.available_count}</TableCell>
                            <TableCell align="right">{row.missing_count}</TableCell>
                            <TableCell align="right">
                              <Chip
                                size="small"
                                label={`${row.missing_rate_pct.toFixed(1)} %`}
                                color={row.missing_rate_pct > 25 ? 'warning' : 'success'}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Stack>
      )}
    </Box>
  );
};
