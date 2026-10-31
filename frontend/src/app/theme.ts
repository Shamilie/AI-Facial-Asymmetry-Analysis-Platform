import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    primary: {
      main: '#123B50',
      light: '#1E5673',
      dark: '#0B2533',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#087E8B',
      light: '#0EA5B5',
      dark: '#055A63',
      contrastText: '#FFFFFF',
    },
    background: {
      default: '#F2F6F8',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#122632',
      secondary: '#475569',
    },
    success: {
      main: '#15803D',
    },
    warning: {
      main: '#B45309',
    },
    error: {
      main: '#B91C1C',
    },
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    h4: { fontWeight: 700, letterSpacing: '-0.01em', color: '#123B50' },
    h5: { fontWeight: 700, letterSpacing: '-0.01em', color: '#123B50' },
    h6: { fontWeight: 600, color: '#123B50' },
    subtitle1: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 1px 3px rgba(18, 59, 80, 0.08), 0 1px 2px rgba(18, 59, 80, 0.04)',
          border: '1px solid #E2E8F0',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: 'none',
          '&:hover': { boxShadow: 'none' },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          backgroundColor: '#F8FAFC',
          color: '#123B50',
          fontWeight: 600,
          fontSize: '0.78rem',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
          borderBottom: '1px solid #CBD5E1',
        },
      },
    },
  },
});
