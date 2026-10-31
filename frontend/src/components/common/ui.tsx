import React from 'react';
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
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import InboxIcon from '@mui/icons-material/Inbox';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export const STATUS_COLORS: Record<
  string,
  { bg: string; fg: string; border: string }
> = {
  Completed: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Approved: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Validated: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Accepted: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Pass: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Healthy: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Obtained: { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC' },
  Active: { bg: '#E0F2FE', fg: '#075985', border: '#7DD3FC' },
  Enrolled: { bg: '#E0F2FE', fg: '#075985', border: '#7DD3FC' },
  Processing: { bg: '#DBEAFE', fg: '#1E40AF', border: '#93C5FD' },
  InProgress: { bg: '#DBEAFE', fg: '#1E40AF', border: '#93C5FD' },
  Calculated: { bg: '#E0F2FE', fg: '#075985', border: '#7DD3FC' },
  ExaminerReviewed: { bg: '#E0F2FE', fg: '#075985', border: '#7DD3FC' },
  Reviewed: { bg: '#E0F2FE', fg: '#075985', border: '#7DD3FC' },
  ReviewRequired: { bg: '#FEF3C7', fg: '#92400E', border: '#FCD34D' },
  RequiresReview: { bg: '#FEF3C7', fg: '#92400E', border: '#FCD34D' },
  Warning: { bg: '#FEF3C7', fg: '#92400E', border: '#FCD34D' },
  Partial: { bg: '#FEF3C7', fg: '#92400E', border: '#FCD34D' },
  LowConfidence: { bg: '#FEF3C7', fg: '#92400E', border: '#FCD34D' },
  Unscaled: { bg: '#FFEDD5', fg: '#9A3412', border: '#FDBA74' },
  Pending: { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' },
  Planned: { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' },
  Scheduled: { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' },
  Queued: { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' },
  AIPredicted: { bg: '#F3E8FF', fg: '#6B21A8', border: '#D8B4FE' },
  Predicted: { bg: '#F3E8FF', fg: '#6B21A8', border: '#D8B4FE' },
  Failed: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
  Fail: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
  Rejected: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
  NotIdentifiable: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
  MissingData: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
  Invalid: { bg: '#FEE2E2', fg: '#991B1B', border: '#FCA5A5' },
};

export const StatusBadge: React.FC<{ status?: string | null; size?: 'small' | 'medium' }> = ({
  status,
  size = 'small',
}) => {
  const key = status || 'Pending';
  const style = STATUS_COLORS[key] || { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1' };
  return (
    <Chip
      size={size}
      label={key}
      sx={{
        backgroundColor: style.bg,
        color: style.fg,
        border: `1px solid ${style.border}`,
        fontWeight: 600,
        fontSize: size === 'small' ? '0.73rem' : '0.8rem',
      }}
    />
  );
};

export const ResearchDisclaimerBanner: React.FC<{ compact?: boolean }> = ({ compact = false }) => (
  <Alert
    severity="info"
    icon={<ScienceIcon fontSize="small" />}
    sx={{
      mb: 2,
      backgroundColor: '#EFF6FF',
      border: '1px solid #BFDBFE',
      color: '#1E3A8A',
      py: compact ? 0.3 : 0.8,
      '& .MuiAlert-message': { fontSize: '0.8rem' },
    }}
  >
    <strong>Research Measurement & Documentation Only:</strong> Quantitative outputs do not
    constitute a medical diagnosis, treatment recommendation, or substitute for clinical judgment.
  </Alert>
);

export const PageHeader: React.FC<{
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}> = ({ title, subtitle, actions }) => (
  <Box
    sx={{
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 2,
      mb: 2.5,
    }}
  >
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 700, color: '#123B50' }}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.3 }}>
          {subtitle}
        </Typography>
      )}
    </Box>
    {actions && <Stack direction="row" spacing={1.2} flexWrap="wrap">{actions}</Stack>}
  </Box>
);

export const PatientContextHeader: React.FC<{
  patientCode?: string;
  patientId?: string;
  fractureSide?: string | null;
  surgeryDate?: string | null;
  studyStatus?: string | null;
  visitType?: string | null;
  visitId?: string | null;
  isSynthetic?: boolean;
}> = (props) => {
  const navigate = useNavigate();
  const ctx = useAuthStore((s) => s.activeContext);
  const code = props.patientCode || ctx.patientCode;
  const pid = props.patientId || ctx.patientId;
  const side = props.fractureSide || ctx.fractureSide;
  const surg = props.surgeryDate || ctx.surgeryDate;
  const status = props.studyStatus || ctx.studyStatus;
  const vtype = props.visitType || ctx.visitType;
  const vid = props.visitId || ctx.visitId;

  if (!code) return null;

  return (
    <Card
      sx={{
        mb: 2.5,
        backgroundColor: '#123B50',
        color: '#FFFFFF',
        border: 'none',
      }}
    >
      <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', md: 'center' }}
          spacing={1.5}
        >
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <Box>
              <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                ACTIVE PATIENT CODE
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#FFFFFF' }}>
                  {code}
                </Typography>
                {props.isSynthetic !== false && code.startsWith('SYNTH') && (
                  <Chip
                    size="small"
                    icon={<WarningAmberIcon sx={{ color: '#FDE68A !important' }} />}
                    label="SYNTHETIC DEMO"
                    sx={{
                      backgroundColor: 'rgba(245, 158, 11, 0.22)',
                      color: '#FDE68A',
                      fontWeight: 600,
                      fontSize: '0.7rem',
                    }}
                  />
                )}
              </Stack>
            </Box>
            <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.18)', pl: 2 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                FRACTURE SIDE
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {side || 'Unilateral'}
              </Typography>
            </Box>
            <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.18)', pl: 2 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                TREATMENT / SURGERY DATE
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {surg || 'Scheduled'}
              </Typography>
            </Box>
            {vtype && (
              <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.18)', pl: 2 }}>
                <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                  ACTIVE VISIT
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, color: '#5EEAD4' }}>
                  {vtype}
                </Typography>
              </Box>
            )}
            <Box sx={{ borderLeft: '1px solid rgba(255,255,255,0.18)', pl: 2 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                RESEARCH STATUS
              </Typography>
              <StatusBadge status={status || 'Active'} />
            </Box>
          </Stack>

          <Stack direction="row" spacing={1} flexWrap="wrap">
            {pid && (
              <Button
                size="small"
                variant="outlined"
                onClick={() => navigate(`/patients/${pid}`)}
                sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.35)' }}
              >
                Patient Workspace
              </Button>
            )}
            {vid && (
              <>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/visits/${vid}/images`)}
                  sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.35)' }}
                >
                  Images
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/ai-analysis/${vid}`)}
                  sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.35)' }}
                >
                  AI Pipeline
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/landmarks/${vid}`)}
                  sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.35)' }}
                >
                  Landmarks
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/measurements/${vid}`)}
                  sx={{ color: '#FFF', borderColor: 'rgba(255,255,255,0.35)' }}
                >
                  Measurements
                </Button>
              </>
            )}
            {pid && (
              <Button
                size="small"
                variant="contained"
                color="secondary"
                onClick={() => navigate(`/follow-up/${pid}`)}
              >
                Follow-up Comparison
              </Button>
            )}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export const KpiCard: React.FC<{
  label: string;
  value: number | string;
  subtitle?: string;
  accent?: string;
  onClick?: () => void;
}> = ({ label, value, subtitle, accent = '#087E8B', onClick }) => (
  <Card
    onClick={onClick}
    sx={{
      cursor: onClick ? 'pointer' : 'default',
      borderTop: `3px solid ${accent}`,
      transition: 'transform 0.12s ease',
      '&:hover': onClick ? { transform: 'translateY(-2px)' } : undefined,
    }}
  >
    <CardContent sx={{ p: 2.2 }}>
      <Typography variant="caption" sx={{ color: '#64748B', fontWeight: 600, textTransform: 'uppercase' }}>
        {label}
      </Typography>
      <Typography variant="h4" sx={{ mt: 0.6, fontWeight: 700, color: '#123B50' }}>
        {value}
      </Typography>
      {subtitle && (
        <Typography variant="caption" color="text.secondary">
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </Card>
);

export const LoadingSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <Card>
    <CardContent>
      <Stack spacing={1.5}>
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} variant="rounded" height={38} />
        ))}
      </Stack>
    </CardContent>
  </Card>
);

export const EmptyState: React.FC<{
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}> = ({ title, description, actionLabel, onAction }) => (
  <Card>
    <CardContent sx={{ textAlign: 'center', py: 5 }}>
      <InboxIcon sx={{ fontSize: 42, color: '#94A3B8', mb: 1 }} />
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {title}
      </Typography>
      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 500, mx: 'auto' }}>
          {description}
        </Typography>
      )}
      {actionLabel && onAction && (
        <Button variant="contained" sx={{ mt: 2 }} onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </CardContent>
  </Card>
);

export const ErrorState: React.FC<{
  message: string;
  onRetry?: () => void;
}> = ({ message, onRetry }) => (
  <Card sx={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2' }}>
    <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
      <Stack direction="row" spacing={1.5} alignItems="center">
        <ErrorOutlineIcon color="error" />
        <Typography variant="body2" color="error.main" sx={{ fontWeight: 500 }}>
          {message}
        </Typography>
      </Stack>
      {onRetry && (
        <Button size="small" variant="outlined" color="error" onClick={onRetry}>
          Retry
        </Button>
      )}
    </CardContent>
  </Card>
);

export const ConfirmationDialog: React.FC<{
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ open, title, message, confirmLabel = 'Confirm', onConfirm, onCancel }) => (
  <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
    <DialogTitle sx={{ fontWeight: 700 }}>{title}</DialogTitle>
    <DialogContent>
      <Typography variant="body2" color="text.secondary">
        {message}
      </Typography>
    </DialogContent>
    <DialogActions sx={{ px: 3, pb: 2 }}>
      <Button onClick={onCancel}>Cancel</Button>
      <Button variant="contained" onClick={onConfirm}>
        {confirmLabel}
      </Button>
    </DialogActions>
  </Dialog>
);
