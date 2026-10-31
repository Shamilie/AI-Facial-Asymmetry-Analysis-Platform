import React, { useState } from 'react';
import {
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
  FormControlLabel,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import ScienceIcon from '@mui/icons-material/Science';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { extractErrorMessage } from '@/services/api';

const DEMO_ACCOUNTS = [
  { role: 'Research Coordinator', email: 'coordinator@faplatform.org', desc: 'Step 1 of Demo: Enroll patients, upload images, start AI' },
  { role: 'Clinician / Examiner', email: 'examiner@faplatform.org', desc: 'Review landmarks, calibrate, approve measurements' },
  { role: 'Principal Investigator', email: 'pi@faplatform.org', desc: 'Protocol governance, approvals, analytics, audit' },
  { role: 'System Administrator', email: 'admin@faplatform.org', desc: 'User management, AI model configuration, monitor' },
  { role: 'Research Analyst', email: 'analyst@faplatform.org', desc: 'Cohort analytics, ICC / Bland-Altman, exports' },
  { role: 'Read-only Researcher', email: 'readonly@faplatform.org', desc: 'View coded research data only' },
];

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  const [email, setEmail] = useState('coordinator@faplatform.org');
  const [password, setPassword] = useState('Research@2026');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !email.includes('@')) {
      setError('Please enter a valid institutional email address.');
      return;
    }
    if (password.length < 4) {
      setError('Please enter your password.');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim(), password, rememberMe);
      navigate('/');
    } catch (err) {
      setError(extractErrorMessage(err, 'Invalid credentials. Please verify your email and password.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: '#F2F6F8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2.5,
      }}
    >
      <Box sx={{ maxWidth: 980, width: '100%', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.08fr 0.92fr' }, gap: 3 }}>
        <Card sx={{ p: { xs: 1, sm: 2 } }}>
          <CardContent>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2.5,
                  bgcolor: '#123B50',
                  color: '#FFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <ScienceIcon />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                  AI Facial Asymmetry Analysis Platform
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Unilateral Mandibular Fracture Longitudinal Research System
                </Typography>
              </Box>
            </Stack>

            <Alert severity="info" sx={{ mb: 2.5, fontSize: '0.78rem' }}>
              Authorized clinical research portal. Outputs are for research measurement and documentation only — not clinical diagnosis.
            </Alert>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit}>
              <Stack spacing={2}>
                <TextField
                  label="Institutional Email"
                  type="email"
                  fullWidth
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <TextField
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  fullWidth
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          aria-label="toggle password visibility"
                          onClick={() => setShowPassword((s) => !s)}
                          edge="end"
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                      />
                    }
                    label={<Typography variant="body2">Remember me</Typography>}
                  />
                  <Button
                    size="small"
                    onClick={() => {
                      setForgotEmail(email);
                      setForgotSent(false);
                      setForgotOpen(true);
                    }}
                  >
                    Forgot password?
                  </Button>
                </Stack>

                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  fullWidth
                  disabled={loading}
                  startIcon={<LockOutlinedIcon />}
                  sx={{ py: 1.3, bgcolor: '#123B50' }}
                >
                  {loading ? 'Signing in...' : 'Sign In to Research Workspace'}
                </Button>
              </Stack>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ bgcolor: '#123B50', color: '#FFFFFF' }}>
          <CardContent sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#FFF', mb: 0.5 }}>
              Quick Demo Role Selector
            </Typography>
            <Typography variant="caption" sx={{ color: '#CBD5E1', display: 'block', mb: 2 }}>
              Click any seeded research role below to prefill credentials (Password: <b>Research@2026</b>)
            </Typography>
            <Divider sx={{ borderColor: 'rgba(255,255,255,0.15)', mb: 2 }} />
            <Stack spacing={1.2}>
              {DEMO_ACCOUNTS.map((acc) => {
                const selected = email.toLowerCase() === acc.email.toLowerCase();
                return (
                  <Box
                    key={acc.email}
                    onClick={() => {
                      setEmail(acc.email);
                      setPassword('Research@2026');
                    }}
                    sx={{
                      p: 1.3,
                      borderRadius: 2,
                      cursor: 'pointer',
                      border: selected ? '1px solid #2DD4BF' : '1px solid rgba(255,255,255,0.14)',
                      backgroundColor: selected ? 'rgba(8, 126, 139, 0.35)' : 'rgba(255,255,255,0.04)',
                      '&:hover': { backgroundColor: 'rgba(8, 126, 139, 0.25)' },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" sx={{ fontWeight: 700, color: '#FFF' }}>
                        {acc.role}
                      </Typography>
                      <Chip
                        size="small"
                        label={acc.email}
                        sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: '#E2E8F0', fontSize: '0.7rem' }}
                      />
                    </Stack>
                    <Typography variant="caption" sx={{ color: '#CBD5E1', display: 'block', mt: 0.3 }}>
                      {acc.desc}
                    </Typography>
                  </Box>
                );
              })}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Dialog open={forgotOpen} onClose={() => setForgotOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Password Reset Request</DialogTitle>
        <DialogContent>
          {forgotSent ? (
            <Alert severity="success" sx={{ mt: 1 }}>
              Password reset instructions have been logged for institutional administrator verification.
              For local demo accounts, use <b>Research@2026</b> or ask a System Administrator in User Management.
            </Alert>
          ) : (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Enter your registered institutional email address to request an administrator-verified password reset.
              </Typography>
              <TextField
                label="Email Address"
                fullWidth
                size="small"
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setForgotOpen(false)}>Close</Button>
          {!forgotSent && (
            <Button variant="contained" onClick={() => setForgotSent(true)}>
              Submit Request
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};
