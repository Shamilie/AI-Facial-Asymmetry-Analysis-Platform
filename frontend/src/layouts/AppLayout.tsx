import React, { useState } from 'react';
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  Divider,
  Drawer,
  IconButton,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Popover,
  Stack,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import DashboardOutlinedIcon from '@mui/icons-material/DashboardOutlined';
import PeopleAltOutlinedIcon from '@mui/icons-material/PeopleAltOutlined';
import EventNoteOutlinedIcon from '@mui/icons-material/EventNoteOutlined';
import CollectionsOutlinedIcon from '@mui/icons-material/CollectionsOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import AdjustOutlinedIcon from '@mui/icons-material/AdjustOutlined';
import ViewInArOutlinedIcon from '@mui/icons-material/ViewInArOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import StraightenOutlinedIcon from '@mui/icons-material/StraightenOutlined';
import CompareArrowsOutlinedIcon from '@mui/icons-material/CompareArrowsOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import MemoryOutlinedIcon from '@mui/icons-material/MemoryOutlined';
import MonitorHeartOutlinedIcon from '@mui/icons-material/MonitorHeartOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import ManageAccountsOutlinedIcon from '@mui/icons-material/ManageAccountsOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import SearchIcon from '@mui/icons-material/Search';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

const SIDEBAR_WIDTH = 256;

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  permissions?: string[];
  roles?: string[];
}

interface NavGroup {
  section: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    section: 'CLINICAL STUDY',
    items: [
      { label: 'Dashboard', path: '/', icon: <DashboardOutlinedIcon fontSize="small" /> },
      {
        label: 'Patients',
        path: '/patients',
        icon: <PeopleAltOutlinedIcon fontSize="small" />,
        permissions: ['patient:read'],
      },
      {
        label: 'Visits',
        path: '/visits',
        icon: <EventNoteOutlinedIcon fontSize="small" />,
        permissions: ['visit:read'],
      },
      {
        label: 'Image Acquisition',
        path: '/images',
        icon: <CollectionsOutlinedIcon fontSize="small" />,
        permissions: ['image:upload', 'image:review'],
      },
    ],
  },
  {
    section: 'AI & QUANTITATIVE ANALYSIS',
    items: [
      {
        label: 'AI Analysis',
        path: '/ai-analysis',
        icon: <PsychologyOutlinedIcon fontSize="small" />,
        permissions: ['ai:run', 'ai:manage'],
      },
      {
        label: 'Landmark Review',
        path: '/landmarks',
        icon: <AdjustOutlinedIcon fontSize="small" />,
        permissions: ['landmark:review', 'landmark:approve'],
      },
      {
        label: '3D Reconstruction',
        path: '/reconstruction',
        icon: <ViewInArOutlinedIcon fontSize="small" />,
        permissions: ['ai:run'],
      },
      {
        label: 'Calibration',
        path: '/calibration',
        icon: <TuneOutlinedIcon fontSize="small" />,
        permissions: ['calibration:write'],
      },
      {
        label: 'Measurements',
        path: '/measurements',
        icon: <StraightenOutlinedIcon fontSize="small" />,
        permissions: ['measurement:read'],
      },
      {
        label: 'Follow-up Comparison',
        path: '/follow-up',
        icon: <CompareArrowsOutlinedIcon fontSize="small" />,
        permissions: ['patient:read'],
      },
    ],
  },
  {
    section: 'RESEARCH OUTPUTS',
    items: [
      {
        label: 'Reports',
        path: '/reports',
        icon: <DescriptionOutlinedIcon fontSize="small" />,
        permissions: ['report:generate', 'report:export'],
      },
      {
        label: 'Research Analytics',
        path: '/analytics',
        icon: <InsightsOutlinedIcon fontSize="small" />,
        permissions: ['analytics:read'],
      },
    ],
  },
  {
    section: 'GOVERNANCE & ADMIN',
    items: [
      {
        label: 'AI Model Configuration',
        path: '/admin/ai-config',
        icon: <MemoryOutlinedIcon fontSize="small" />,
        permissions: ['config:manage'],
      },
      {
        label: 'AI Execution Monitor',
        path: '/admin/ai-monitor',
        icon: <MonitorHeartOutlinedIcon fontSize="small" />,
        permissions: ['ai:manage', 'config:manage'],
      },
      {
        label: 'Protocol Configuration',
        path: '/admin/protocols',
        icon: <ScienceOutlinedIcon fontSize="small" />,
        permissions: ['protocol:manage'],
      },
      {
        label: 'User Management',
        path: '/admin/users',
        icon: <ManageAccountsOutlinedIcon fontSize="small" />,
        permissions: ['user:manage'],
      },
      {
        label: 'Audit Logs',
        path: '/admin/audit-logs',
        icon: <FactCheckOutlinedIcon fontSize="small" />,
        permissions: ['audit:read'],
      },
    ],
  },
  {
    section: 'SYSTEM & PREFERENCES',
    items: [
      {
        label: 'Settings',
        path: '/settings',
        icon: <SettingsOutlinedIcon fontSize="small" />,
      },
    ],
  },
];

export const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [notifAnchor, setNotifAnchor] = useState<HTMLElement | null>(null);

  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await api.get('/notifications');
      return res.data.data || [];
    },
  });

  const unreadCount = notifications.filter((n: any) => !n.is_read).length;

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchText.trim()) {
      navigate(`/patients?search=${encodeURIComponent(searchText.trim())}`);
    }
  };

  const isItemVisible = (item: NavItem): boolean => {
    if (!user) return false;
    if (user.is_superuser) return true;
    if (!item.permissions && !item.roles) return true;
    const hasPerm = item.permissions ? item.permissions.some((p) => user.permissions?.includes(p)) : false;
    const hasRole = item.roles ? item.roles.some((r) => user.roles?.includes(r)) : false;
    return hasPerm || hasRole;
  };

  const visibleGroups = NAV_GROUPS.map((grp) => ({
    ...grp,
    items: grp.items.filter(isItemVisible),
  })).filter((grp) => grp.items.length > 0);

  const currentTitle = (() => {
    for (const grp of visibleGroups) {
      for (const item of grp.items) {
        if (isActive(item.path)) return item.label;
      }
    }
    return 'Research Workspace';
  })();

  const drawerContent = (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#123B50',
        color: '#FFFFFF',
      }}
    >
      <Box sx={{ px: 2.5, py: 2.2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: 2,
            backgroundColor: '#087E8B',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 800,
            fontSize: '0.95rem',
            color: '#FFF',
          }}
        >
          FA
        </Box>
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.2, color: '#FFF' }}>
            Facial Asymmetry
          </Typography>
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: '0.7rem' }}>
            Mandibular Fracture Research
          </Typography>
        </Box>
      </Box>
      <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />

      <Box sx={{ flex: 1, overflowY: 'auto', py: 1 }}>
        {visibleGroups.map((grp) => (
          <Box key={grp.section} sx={{ mb: 1.2 }}>
            <Typography
              variant="caption"
              sx={{
                px: 2.5,
                py: 0.6,
                display: 'block',
                color: '#94A3B8',
                fontWeight: 700,
                fontSize: '0.67rem',
                letterSpacing: '0.06em',
              }}
            >
              {grp.section}
            </Typography>
            <List dense disablePadding>
              {grp.items.map((item) => {
                const active = isActive(item.path);
                return (
                  <ListItemButton
                    key={item.path}
                    onClick={() => {
                      navigate(item.path);
                      setMobileOpen(false);
                    }}
                    sx={{
                      mx: 1.2,
                      my: 0.2,
                      borderRadius: 1.5,
                      py: 0.75,
                      backgroundColor: active ? '#087E8B' : 'transparent',
                      color: active ? '#FFFFFF' : '#CBD5E1',
                      '&:hover': {
                        backgroundColor: active ? '#087E8B' : 'rgba(255,255,255,0.07)',
                        color: '#FFFFFF',
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 32, color: 'inherit' }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{
                        fontSize: '0.83rem',
                        fontWeight: active ? 600 : 500,
                      }}
                    />
                  </ListItemButton>
                );
              })}
            </List>
          </Box>
        ))}
      </Box>

      <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block', fontSize: '0.69rem' }}>
          Protocol UMF-ASYM-2026 v1.0
        </Typography>
        <Typography variant="caption" sx={{ color: '#64748B', fontSize: '0.66rem' }}>
          Non-diagnostic research build
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F2F6F8' }}>
      <Box component="nav" sx={{ width: { md: SIDEBAR_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { width: SIDEBAR_WIDTH, boxSizing: 'border-box' },
          }}
        >
          {drawerContent}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              width: SIDEBAR_WIDTH,
              boxSizing: 'border-box',
              borderRight: 'none',
            },
          }}
        >
          {drawerContent}
        </Drawer>
      </Box>

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            backgroundColor: '#FFFFFF',
            color: '#123B50',
            borderBottom: '1px solid #E2E8F0',
          }}
        >
          <Toolbar sx={{ gap: 2, minHeight: 64 }}>
            <IconButton
              edge="start"
              onClick={() => setMobileOpen(true)}
              sx={{ display: { md: 'none' } }}
            >
              <MenuIcon />
            </IconButton>

            <Box sx={{ flexGrow: 1 }}>
              <Breadcrumbs aria-label="breadcrumb" sx={{ fontSize: '0.75rem' }}>
                <Typography
                  variant="caption"
                  sx={{ cursor: 'pointer', color: '#64748B' }}
                  onClick={() => navigate('/')}
                >
                  Platform
                </Typography>
                <Typography variant="caption" sx={{ color: '#123B50', fontWeight: 600 }}>
                  {currentTitle}
                </Typography>
              </Breadcrumbs>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                {currentTitle}
              </Typography>
            </Box>

            <Box component="form" onSubmit={handleGlobalSearch} sx={{ display: { xs: 'none', sm: 'block' } }}>
              <TextField
                size="small"
                placeholder="Search coded patient (e.g. SYNTH-UMF-001)..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                sx={{ width: 290, backgroundColor: '#F8FAFC' }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" sx={{ color: '#64748B' }} />
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            <Tooltip title="Notifications">
              <IconButton onClick={(e) => setNotifAnchor(e.currentTarget)}>
                <Badge badgeContent={unreadCount} color="secondary">
                  <NotificationsNoneIcon />
                </Badge>
              </IconButton>
            </Tooltip>

            <Popover
              open={Boolean(notifAnchor)}
              anchorEl={notifAnchor}
              onClose={() => setNotifAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
              <Box sx={{ width: 340, p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Research Notifications
                </Typography>
                <Divider sx={{ mb: 1 }} />
                {notifications.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No notifications
                  </Typography>
                ) : (
                  <Stack spacing={1}>
                    {notifications.slice(0, 6).map((n: any) => (
                      <Box
                        key={n.id}
                        sx={{
                          p: 1,
                          borderRadius: 1,
                          backgroundColor: n.is_read ? '#F8FAFC' : '#EFF6FF',
                        }}
                      >
                        <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
                          {n.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {n.message}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                )}
              </Box>
            </Popover>

            <Stack direction="row" spacing={1.2} alignItems="center">
              <Avatar sx={{ width: 32, height: 32, bgcolor: '#123B50', fontSize: '0.8rem' }}>
                {(user?.full_name || 'R')[0].toUpperCase()}
              </Avatar>
              <Box sx={{ display: { xs: 'none', lg: 'block' } }}>
                <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.1 }}>
                  {user?.full_name}
                </Typography>
                <Chip
                  size="small"
                  label={user?.primary_role || 'Researcher'}
                  sx={{
                    height: 18,
                    fontSize: '0.67rem',
                    fontWeight: 600,
                    bgcolor: '#E0F2FE',
                    color: '#075985',
                  }}
                />
              </Box>
              <Tooltip title="Sign out">
                <Button
                  size="small"
                  variant="outlined"
                  color="inherit"
                  startIcon={<LogoutIcon fontSize="small" />}
                  onClick={async () => {
                    await logout();
                    navigate('/login');
                  }}
                >
                  Logout
                </Button>
              </Tooltip>
            </Stack>
          </Toolbar>
        </AppBar>

        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: { xs: 2, md: 3.5 },
            maxWidth: 1600,
            width: '100%',
            mx: 'auto',
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
};
