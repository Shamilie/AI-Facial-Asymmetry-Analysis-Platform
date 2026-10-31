import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid2 as Grid,
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
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, extractErrorMessage } from '@/services/api';
import {
  ErrorState,
  KpiCard,
  LoadingSkeleton,
  PageHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';
import { useAuthStore } from '@/store/authStore';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const setActiveContext = useAuthStore((s) => s.setActiveContext);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard-summary', dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get('/dashboard/summary', { params });
      return res.data.data;
    },
  });

  if (isLoading) return <LoadingSkeleton rows={8} />;
  if (error || !data) {
    return <ErrorState message={extractErrorMessage(error)} onRetry={() => refetch()} />;
  }

  const kpis = data.kpis;

  return (
    <Box>
      <ResearchDisclaimerBanner compact />
      <PageHeader
        title="Clinical Research Overview Dashboard"
        subtitle="Longitudinal facial asymmetry monitoring for unilateral mandibular fractures treated by fixation"
        actions={
          <>
            <TextField
              size="small"
              type="date"
              label="Enrolled From"
              InputLabelProps={{ shrink: true }}
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              sx={{ bgcolor: '#FFF' }}
            />
            <TextField
              size="small"
              type="date"
              label="Enrolled To"
              InputLabelProps={{ shrink: true }}
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              sx={{ bgcolor: '#FFF' }}
            />
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/patients/new')}
            >
              Register Coded Patient
            </Button>
          </>
        }
      />

      {/* Top 6 KPI cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="Total Patients"
            value={kpis.total_patients}
            subtitle="Coded study cohort"
            accent="#123B50"
            onClick={() => navigate('/patients')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="Active Patients"
            value={kpis.active_patients}
            subtitle="In longitudinal follow-up"
            accent="#087E8B"
            onClick={() => navigate('/patients')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="Completed Follow-ups"
            value={kpis.completed_follow_ups}
            subtitle="Approved study visits"
            accent="#15803D"
            onClick={() => navigate('/visits')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="Pending Follow-ups"
            value={kpis.pending_follow_ups}
            subtitle="Scheduled / images pending"
            accent="#0284C7"
            onClick={() => navigate('/visits')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="AI Analyses Completed"
            value={kpis.ai_analyses_completed}
            subtitle="Executed pipeline stages"
            accent="#7C3AED"
            onClick={() => navigate('/admin/ai-monitor')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
          <KpiCard
            label="Requiring Review"
            value={kpis.analyses_requiring_review}
            subtitle="Awaiting examiner sign-off"
            accent="#D97706"
            onClick={() => navigate('/measurements')}
          />
        </Grid>
      </Grid>

      {/* Charts row */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, lg: 5 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                1. Patient Enrollment Trend
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Monthly coded participant enrollment derived from study database
              </Typography>
              <Box sx={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.enrollment_chart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis allowDecimals={false} fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="patients" name="Enrolled Patients" fill="#123B50" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, lg: 7 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                2. Longitudinal Follow-up Completion by Protocol Stage
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Pre-op, 1-week, 6-week, 3-month, and 6-month visit status distribution
              </Typography>
              <Box sx={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.follow_up_completion_chart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="stage" fontSize={12} />
                    <YAxis allowDecimals={false} fontSize={12} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="completed" name="Completed" stackId="a" fill="#15803D" />
                    <Bar dataKey="review_required" name="Review Required" stackId="a" fill="#D97706" />
                    <Bar dataKey="pending" name="Scheduled / Pending" stackId="a" fill="#94A3B8" />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent patients + Pending Examiner Reviews */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, lg: 7 }}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  3. Recent Coded Patients
                </Typography>
                <Button size="small" onClick={() => navigate('/patients')}>
                  View All Patients
                </Button>
              </Stack>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Patient Code</TableCell>
                      <TableCell>Fracture Side</TableCell>
                      <TableCell>Surgery Date</TableCell>
                      <TableCell>Visits</TableCell>
                      <TableCell>Analysis</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.recent_patients.map((p: any) => (
                      <TableRow key={p.id} hover>
                        <TableCell>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                              {p.patient_code}
                            </Typography>
                            {p.is_synthetic && (
                              <Chip size="small" label="DEMO" sx={{ height: 18, fontSize: '0.65rem' }} />
                            )}
                          </Stack>
                        </TableCell>
                        <TableCell>{p.fracture_side}</TableCell>
                        <TableCell>{p.surgery_date || '—'}</TableCell>
                        <TableCell>
                          {p.completed_visits}/{p.total_visits}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={p.analysis_status} />
                        </TableCell>
                        <TableCell align="right">
                          <Button
                            size="small"
                            onClick={() => {
                              setActiveContext({
                                patientId: p.id,
                                patientCode: p.patient_code,
                                fractureSide: p.fracture_side,
                                surgeryDate: p.surgery_date,
                                studyStatus: p.study_status,
                              });
                              navigate(`/patients/${p.id}`);
                            }}
                          >
                            Open
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, lg: 5 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  7. Pending Examiner Reviews
                </Typography>
                <StatusBadge status="ReviewRequired" />
              </Stack>
              {data.pending_examiner_reviews.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No visits currently awaiting examiner review.
                </Typography>
              ) : (
                <Stack spacing={1.2}>
                  {data.pending_examiner_reviews.map((item: any) => (
                    <Box
                      key={item.visit_id}
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        border: '1px solid #FDE68A',
                        backgroundColor: '#FFFBEB',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                          {item.patient_code} — {item.visit_type}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Visit Date: {item.actual_date || 'Recorded'}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => {
                            setActiveContext({
                              patientId: item.patient_id,
                              patientCode: item.patient_code,
                              visitId: item.visit_id,
                              visitType: item.visit_type,
                            });
                            navigate(`/landmarks/${item.visit_id}`);
                          }}
                        >
                          Landmarks
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          color="secondary"
                          startIcon={<FactCheckIcon fontSize="small" />}
                          onClick={() => {
                            setActiveContext({
                              patientId: item.patient_id,
                              patientCode: item.patient_code,
                              visitId: item.visit_id,
                              visitType: item.visit_type,
                            });
                            navigate(`/measurements/${item.visit_id}`);
                          }}
                        >
                          Review
                        </Button>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}

              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                5. AI Processing Status Breakdown
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {data.ai_processing_status.map((s: any) => (
                  <Chip
                    key={s.status}
                    label={`${s.status}: ${s.count}`}
                    size="small"
                    sx={{ fontWeight: 600 }}
                  />
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Upcoming visits + Recent activity */}
      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                4. Upcoming Follow-up Visits
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Patient</TableCell>
                      <TableCell>Stage</TableCell>
                      <TableCell>Planned Date</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.upcoming_visits.map((v: any) => (
                      <TableRow key={v.visit_id} hover>
                        <TableCell sx={{ fontWeight: 600 }}>{v.patient_code}</TableCell>
                        <TableCell>{v.visit_type}</TableCell>
                        <TableCell>{v.planned_date}</TableCell>
                        <TableCell>
                          <StatusBadge status={v.status} />
                        </TableCell>
                        <TableCell align="right">
                          <Button
                            size="small"
                            startIcon={<PlayArrowIcon fontSize="small" />}
                            onClick={() => {
                              setActiveContext({
                                patientId: v.patient_id,
                                patientCode: v.patient_code,
                                visitId: v.visit_id,
                                visitType: v.visit_type,
                              });
                              navigate(`/visits/${v.visit_id}/images`);
                            }}
                          >
                            Acquire Images
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  6. Recent Audit & Research Activity
                </Typography>
                <Button size="small" onClick={() => navigate('/admin/audit-logs')}>
                  Full Audit Log
                </Button>
              </Stack>
              <Stack spacing={1}>
                {data.recent_activity.map((act: any) => (
                  <Box
                    key={act.id}
                    sx={{
                      p: 1.1,
                      borderRadius: 1.5,
                      backgroundColor: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#123B50' }}>
                        {act.action} ({act.resource_type})
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(act.created_at).toLocaleString()}
                      </Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      User: {act.user_email} {act.reason ? `— ${act.reason}` : ''}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
