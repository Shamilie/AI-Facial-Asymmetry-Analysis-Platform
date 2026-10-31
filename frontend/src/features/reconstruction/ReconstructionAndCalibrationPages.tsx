import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Divider,
  FormControl,
  FormControlLabel,
  Grid2 as Grid,
  InputLabel,
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
  Typography,
} from '@mui/material';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import DownloadIcon from '@mui/icons-material/Download';
import StraightenIcon from '@mui/icons-material/Straighten';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import * as THREE from 'three';
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
import { CalibrationItem, VisitImageRecord, VisitSummary } from '@/types';
import { useAuthStore } from '@/store/authStore';

// ============================================================================
// PAGE 10: 3D Face Reconstruction Workspace
// ============================================================================
export const ReconstructionWorkspacePage: React.FC = () => {
  const { visitId } = useParams<{ visitId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeVisitId = useAuthStore((s) => s.activeContext.visitId);
  const resolvedVisitId = visitId || activeVisitId || '';

  const [selectedVisitId, setSelectedVisitId] = useState<string>(resolvedVisitId);
  const [wireframe, setWireframe] = useState<boolean>(false);
  const [showLandmarks, setShowLandmarks] = useState<boolean>(true);
  const [showPaths, setShowPaths] = useState<boolean>(true);
  const [cameraPreset, setCameraPreset] = useState<'front' | 'right' | 'left'>('front');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const mountRef = useRef<HTMLDivElement | null>(null);

  const visitsQuery = useQuery({
    queryKey: ['visits-for-recon'],
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

  const reconQuery = useQuery({
    queryKey: ['visit-reconstruction', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/reconstruction/visits/${selectedVisitId}`);
      return res.data.data as {
        id: string;
        visit_id: string;
        provider: string;
        model_name: string;
        model_version: string;
        status: string;
        coverage_status: string;
        quality_score: number;
        vertex_count: number;
        face_count: number;
        scale_factor_mm: number | null;
        is_calibrated: boolean;
        is_synthetic: boolean;
        landmarks_3d: Record<string, [number, number, number]>;
        surface_paths: Record<string, { distance_mm: number | null; path_points: number[][] }>;
        warnings: string[];
        mesh_payload: {
          vertices: number[][];
          faces: number[][];
        } | null;
        obj_download_url: string;
        ply_download_url: string;
      } | null;
    },
  });

  const generateMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/reconstruction/visits/${selectedVisitId}/generate`);
      return res.data.data;
    },
    onSuccess: () => {
      setMsg({ type: 'success', text: '3D facial mesh and geodesic paths regenerated.' });
      queryClient.invalidateQueries({ queryKey: ['visit-reconstruction', selectedVisitId] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  // Render interactive Three.js 3D mesh scene
  useEffect(() => {
    const container = mountRef.current;
    const meshData = reconQuery.data?.mesh_payload;
    if (!container || !meshData || !meshData.vertices?.length) return;

    const width = container.clientWidth || 640;
    const height = 500;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#0B192C');

    const camera = new THREE.PerspectiveCamera(42, width / height, 1, 2000);
    if (cameraPreset === 'front') {
      camera.position.set(0, 0, 290);
    } else if (cameraPreset === 'right') {
      camera.position.set(260, 0, 110);
    } else {
      camera.position.set(-260, 0, 110);
    }
    camera.lookAt(0, 0, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      // Fallback when WebGL context is unavailable in headless environment
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambientLight);
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.9);
    dirLight1.position.set(120, 150, 250);
    scene.add(dirLight1);
    const dirLight2 = new THREE.DirectionalLight(0x5eead4, 0.35);
    dirLight2.position.set(-140, -100, 160);
    scene.add(dirLight2);

    const rootGroup = new THREE.Group();
    scene.add(rootGroup);

    // Build BufferGeometry from vertices and faces
    const geometry = new THREE.BufferGeometry();
    const flatPositions: number[] = [];
    meshData.vertices.forEach((v) => {
      flatPositions.push(v[0], v[1], v[2]);
    });
    const indices: number[] = [];
    meshData.faces.forEach((f) => {
      indices.push(f[0], f[1], f[2]);
    });

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(flatPositions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      color: 0xe2c1a8,
      roughness: 0.48,
      metalness: 0.08,
      side: THREE.DoubleSide,
      wireframe,
    });
    const faceMesh = new THREE.Mesh(geometry, material);
    rootGroup.add(faceMesh);

    // Render 3D anatomical landmarks
    if (showLandmarks && reconQuery.data?.landmarks_3d) {
      const sphereGeo = new THREE.SphereGeometry(2.6, 16, 16);
      Object.entries(reconQuery.data.landmarks_3d).forEach(([code, pt]) => {
        const isMidline = ['Tr', 'G', 'N', 'Prn', 'Sn', 'Ls', 'Li', 'Pg', 'Gn', 'Me'].includes(code);
        const lmMat = new THREE.MeshBasicMaterial({
          color: isMidline ? 0x38bdf8 : code.endsWith('_R') ? 0xf59e0b : 0x10b981,
        });
        const sp = new THREE.Mesh(sphereGeo, lmMat);
        sp.position.set(pt[0], pt[1], pt[2] + 1.5);
        rootGroup.add(sp);
      });
    }

    // Render geodesic surface paths
    if (showPaths && reconQuery.data?.surface_paths) {
      Object.entries(reconQuery.data.surface_paths).forEach(([key, pathInfo]) => {
        if (!pathInfo.path_points || pathInfo.path_points.length < 2) return;
        const pts = pathInfo.path_points.map((p) => new THREE.Vector3(p[0], p[1], p[2] + 2.0));
        const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
        const lineMat = new THREE.LineBasicMaterial({
          color: key.endsWith('_R') ? 0xf97316 : 0x2dd4bf,
          linewidth: 2,
        });
        const line = new THREE.Line(lineGeo, lineMat);
        rootGroup.add(line);
      });
    }

    // Mouse drag rotation + wheel zoom
    let isDragging = false;
    let prevX = 0;
    let prevY = 0;

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - prevX;
      const dy = e.clientY - prevY;
      rootGroup.rotation.y += dx * 0.008;
      rootGroup.rotation.x += dy * 0.008;
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onMouseUp = () => {
      isDragging = false;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.position.z = Math.max(130, Math.min(480, camera.position.z + e.deltaY * 0.18));
    };

    const domElem = renderer.domElement;
    domElem.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    domElem.addEventListener('wheel', onWheel, { passive: false });

    let frameId = 0;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frameId);
      domElem.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      domElem.removeEventListener('wheel', onWheel);
      renderer.dispose();
    };
  }, [reconQuery.data, wireframe, showLandmarks, showPaths, cameraPreset]);

  const activeVisitObj = (visitsQuery.data || []).find((v) => v.id === selectedVisitId);
  const recon = reconQuery.data;

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
        title="3D Face Reconstruction & Geodesic Surface Workspace"
        subtitle="Multi-view 3D surface mesh synthesis, 3D landmark projection, and Dijkstra surface geodesic path approximation"
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
              startIcon={<RefreshIcon />}
              disabled={!selectedVisitId || generateMut.isPending}
              onClick={() => generateMut.mutate()}
            >
              Regenerate 3D Mesh
            </Button>
            {recon && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  component="a"
                  href={withAuthTokenUrl(recon.obj_download_url)}
                  target="_blank"
                >
                  Export .OBJ
                </Button>
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<DownloadIcon />}
                  component="a"
                  href={withAuthTokenUrl(recon.ply_download_url)}
                  target="_blank"
                >
                  Export .PLY
                </Button>
              </>
            )}
          </>
        }
      />

      <Alert severity="warning" sx={{ mb: 2 }}>
        <strong>3D Geodesic Methodological Notice:</strong> 3D surface geodesic paths (e.g., Tragus–Subnasale and Tragus–Pogonion) are computational approximations of clinical flexible-tape facial measurements. They depend on multi-view camera coverage and physical scale calibration and require paired validation against direct clinical caliper/tape measurements.
      </Alert>

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      {reconQuery.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : reconQuery.isError ? (
        <ErrorState message={extractErrorMessage(reconQuery.error)} onRetry={() => reconQuery.refetch()} />
      ) : !recon ? (
        <EmptyState
          title="No 3D face reconstruction generated for this visit yet"
          description="Click 'Regenerate 3D Mesh' or run the full AI pipeline to synthesize a 3D surface mesh from the visit photographs."
          actionLabel="Generate 3D Mesh Now"
          onAction={() => generateMut.mutate()}
        />
      ) : (
        <Grid container spacing={2.5}>
          {/* 3D Interactive Viewport */}
          <Grid size={{ xs: 12, lg: 8 }}>
            <Card>
              <CardContent>
                <Stack
                  direction="row"
                  justifyContent="space-between"
                  alignItems="center"
                  flexWrap="wrap"
                  spacing={1}
                  sx={{ mb: 1.5 }}
                >
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant={cameraPreset === 'front' ? 'contained' : 'outlined'}
                      onClick={() => setCameraPreset('front')}
                    >
                      Frontal View
                    </Button>
                    <Button
                      size="small"
                      variant={cameraPreset === 'right' ? 'contained' : 'outlined'}
                      onClick={() => setCameraPreset('right')}
                    >
                      Right Profile
                    </Button>
                    <Button
                      size="small"
                      variant={cameraPreset === 'left' ? 'contained' : 'outlined'}
                      onClick={() => setCameraPreset('left')}
                    >
                      Left Profile
                    </Button>
                  </Stack>

                  <Stack direction="row" spacing={1.5}>
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={wireframe}
                          onChange={(e) => setWireframe(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">Wireframe</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={showLandmarks}
                          onChange={(e) => setShowLandmarks(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">3D Landmarks</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={showPaths}
                          onChange={(e) => setShowPaths(e.target.checked)}
                        />
                      }
                      label={<Typography variant="caption">Geodesic Paths</Typography>}
                    />
                  </Stack>
                </Stack>

                <Box
                  ref={mountRef}
                  sx={{
                    width: '100%',
                    height: 500,
                    borderRadius: 2,
                    overflow: 'hidden',
                    backgroundColor: '#0B192C',
                    border: '1px solid #1E293B',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#94A3B8',
                  }}
                >
                  <Typography variant="body2">Initializing 3D WebGL Mesh Viewport...</Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Controls: Left-drag to rotate mesh in 3D space • Mouse wheel to zoom • Toggle wireframe, 3D landmarks (blue=midline, orange=right, green=left), and geodesic surface paths.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Mesh Coverage, Quality & Geodesic Path Summary */}
          <Grid size={{ xs: 12, lg: 4 }}>
            <Stack spacing={2}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                    Reconstruction Quality & Coverage
                  </Typography>
                  <Stack spacing={1.2}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" color="text.secondary">
                        Reconstruction Status
                      </Typography>
                      <StatusBadge status={recon.status} />
                    </Stack>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" color="text.secondary">
                        Anatomical Coverage
                      </Typography>
                      <StatusBadge status={recon.coverage_status} />
                    </Stack>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" color="text.secondary">
                        Physical Scale Status
                      </Typography>
                      <StatusBadge status={recon.is_calibrated ? 'Pass' : 'Unscaled'} />
                    </Stack>
                    <Divider />
                    <Typography variant="body2">
                      <strong>Provider / Model:</strong> {recon.provider} — {recon.model_name} ({recon.model_version})
                    </Typography>
                    <Typography variant="body2">
                      <strong>Mesh Topology:</strong> {recon.vertex_count} vertices • {recon.face_count} triangles
                    </Typography>
                    <Typography variant="body2">
                      <strong>Quality Score:</strong> {(recon.quality_score * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant="body2">
                      <strong>Scale Factor:</strong>{' '}
                      {recon.scale_factor_mm ? `${recon.scale_factor_mm.toFixed(4)} mm/px` : 'Unscaled'}
                    </Typography>
                  </Stack>

                  {recon.warnings?.map((w, i) => (
                    <Alert key={i} severity="warning" sx={{ mt: 1.5, py: 0.3, '& .MuiAlert-message': { fontSize: '0.75rem' } }}>
                      {w}
                    </Alert>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                    3D Surface Geodesic Paths
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Geodesic Path</TableCell>
                          <TableCell align="right">Surface Distance</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.entries(recon.surface_paths || {}).map(([code, p]) => (
                          <TableRow key={code}>
                            <TableCell sx={{ fontWeight: 600 }}>{code}</TableCell>
                            <TableCell align="right">
                              {p.distance_mm != null
                                ? `${p.distance_mm.toFixed(2)} ${recon.is_calibrated ? 'mm' : 'units (Unscaled)'}`
                                : 'Missing'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Stack>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

// ============================================================================
// PAGE 11: Calibration and Scale Management Screen
// ============================================================================
export const CalibrationWorkspacePage: React.FC = () => {
  const { visitId } = useParams<{ visitId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeVisitId = useAuthStore((s) => s.activeContext.visitId);
  const resolvedVisitId = visitId || activeVisitId || '';

  const [selectedVisitId, setSelectedVisitId] = useState<string>(resolvedVisitId);
  const [calType, setCalType] = useState<'FrontalPhoto' | 'RightLateralPhoto' | 'LeftLateralPhoto' | 'OPG'>(
    'FrontalPhoto'
  );
  const [markerType, setMarkerType] = useState<string>('FiducialForeheadSticker_20mm');
  const [knownMm, setKnownMm] = useState<number>(20.0);
  const [measuredPx, setMeasuredPx] = useState<number>(110.0);
  const [markerLocation, setMarkerLocation] = useState<string>('Forehead / Frontal Facial Plane');
  const [calibrationPlane, setCalibrationPlane] = useState<string>('Coronal Facial Plane');
  const [samePlaneConfirmed, setSamePlaneConfirmed] = useState<boolean>(true);
  const [isPhysical, setIsPhysical] = useState<boolean>(true);
  const [magnificationFactor, setMagnificationFactor] = useState<number>(1.2);
  const [notes, setNotes] = useState<string>('Verified physical fiducial ruler in same anatomical plane');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Two-point interactive pixel ruler on image preview
  const [ptA, setPtA] = useState<{ x: number; y: number }>({ x: 345, y: 120 });
  const [ptB, setPtB] = useState<{ x: number; y: number }>({ x: 455, y: 120 });
  const [clickTarget, setClickTarget] = useState<'A' | 'B'>('A');

  const visitsQuery = useQuery({
    queryKey: ['visits-for-calibration'],
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

  const calibrationsQuery = useQuery({
    queryKey: ['visit-calibrations', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/calibration/visits/${selectedVisitId}`);
      return res.data.data as CalibrationItem[];
    },
  });

  const imagesQuery = useQuery({
    queryKey: ['visit-images-cal', selectedVisitId],
    enabled: Boolean(selectedVisitId),
    queryFn: async () => {
      const res = await api.get(`/images/visits/${selectedVisitId}`);
      return res.data.data as VisitImageRecord[];
    },
  });

  const activeCalForType = useMemo(
    () => (calibrationsQuery.data || []).find((c) => c.calibration_type === calType && c.is_active),
    [calibrationsQuery.data, calType]
  );

  useEffect(() => {
    if (activeCalForType) {
      setMarkerType(activeCalForType.reference_marker_type);
      setKnownMm(activeCalForType.known_marker_length_mm);
      setMeasuredPx(activeCalForType.measured_marker_length_px);
      setMarkerLocation(activeCalForType.marker_location || '');
      setCalibrationPlane(activeCalForType.calibration_plane || '');
      setSamePlaneConfirmed(activeCalForType.same_plane_confirmed);
      setIsPhysical(activeCalForType.is_physical);
      if (activeCalForType.magnification_factor) {
        setMagnificationFactor(activeCalForType.magnification_factor);
      }
    } else if (calType === 'OPG') {
      setMarkerType('OPG_MetallicBallBearing_5mm');
      setKnownMm(25.0);
      setMeasuredPx(125.0);
      setMarkerLocation('Mandibular Arch / Bite Block');
      setCalibrationPlane('Panoramic Focal Trough');
      setMagnificationFactor(1.2);
    } else {
      setMarkerType('FiducialForeheadSticker_20mm');
      setKnownMm(20.0);
      setMeasuredPx(110.0);
      setMarkerLocation(calType === 'FrontalPhoto' ? 'Forehead' : 'Preauricular / Zygomatic Arch');
      setCalibrationPlane(calType === 'FrontalPhoto' ? 'Coronal Facial Plane' : 'Sagittal Lateral Plane');
    }
  }, [calType, activeCalForType?.id]);

  const matchingImage = useMemo(() => {
    const mapType: Record<string, string> = {
      FrontalPhoto: 'Frontal',
      RightLateralPhoto: 'RightLateral',
      LeftLateralPhoto: 'LeftLateral',
      OPG: 'OPG',
    };
    const target = mapType[calType];
    return (imagesQuery.data || []).find((i) => i.image_type === target) || null;
  }, [imagesQuery.data, calType]);

  const saveCalMut = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/calibration/visits/${selectedVisitId}`, {
        image_id: matchingImage?.id || null,
        calibration_type: calType,
        reference_marker_type: markerType,
        known_marker_length_mm: Number(knownMm),
        measured_marker_length_px: Number(measuredPx),
        marker_location: markerLocation,
        calibration_plane: calibrationPlane,
        calibration_method: 'InteractiveTwoPointFiducial',
        magnification_factor: calType === 'OPG' ? Number(magnificationFactor) : null,
        pixel_spacing_x: calType === 'OPG' ? Number((knownMm / measuredPx).toFixed(5)) : null,
        pixel_spacing_y: calType === 'OPG' ? Number((knownMm / measuredPx).toFixed(5)) : null,
        regional_calibration:
          calType === 'OPG' ? { ramus_factor: 1.0, body_factor: 1.0, condyle_factor: 1.0 } : null,
        is_physical: isPhysical,
        same_plane_confirmed: samePlaneConfirmed,
        notes,
        recalculate_measurements: true,
      });
      return res.data.data;
    },
    onSuccess: (data) => {
      setMsg({
        type: 'success',
        text: `Saved ${calType} calibration (${data.mm_per_pixel.toFixed(5)} mm/px, v${data.version}) and recalculated dependent visit measurements.`,
      });
      queryClient.invalidateQueries({ queryKey: ['visit-calibrations', selectedVisitId] });
      queryClient.invalidateQueries({ queryKey: ['visit-measurements', selectedVisitId] });
    },
    onError: (err) => setMsg({ type: 'error', text: extractErrorMessage(err) }),
  });

  const computedMmPerPx = measuredPx > 0 ? knownMm / measuredPx : 0;
  const activeVisitObj = (visitsQuery.data || []).find((v) => v.id === selectedVisitId);

  const handleRulerSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const w = matchingImage?.width || (calType === 'OPG' ? 1200 : 800);
    const h = matchingImage?.height || (calType === 'OPG' ? 720 : 900);
    const x = Math.round(((e.clientX - rect.left) / rect.width) * w);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * h);
    if (clickTarget === 'A') {
      setPtA({ x, y });
      setClickTarget('B');
    } else {
      setPtB({ x, y });
      setClickTarget('A');
      const dist = Math.hypot(x - ptA.x, y - ptA.y);
      if (dist > 1) {
        setMeasuredPx(Number(dist.toFixed(2)));
      }
    }
  };

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
        title="View-Specific Physical Calibration & Scale Management"
        subtitle="Configure physical fiducial calibration per photographic view and OPG magnification parameters"
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
              startIcon={<StraightenIcon />}
              onClick={() => navigate(`/measurements/${selectedVisitId}`)}
            >
              Go to Measurements
            </Button>
          </>
        }
      />

      <Alert severity="error" sx={{ mb: 2 }}>
        <strong>Mandatory Calibration Rule:</strong> Generic screen/CSS PPI assumptions (such as{' '}
        <code>1 mm = 3.78 px</code>) are strictly prohibited for clinical research millimeter measurements. Each view (Frontal, Right Lateral, Left Lateral) requires an independent physical calibration marker in the anatomical plane, and OPG requires machine magnification correction.
      </Alert>

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      <Grid container spacing={2.5}>
        {/* Left Form: Calibration Configuration */}
        <Grid size={{ xs: 12, lg: 5 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
                Configure View Calibration
              </Typography>

              <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 2 }}>
                {(['FrontalPhoto', 'RightLateralPhoto', 'LeftLateralPhoto', 'OPG'] as const).map((t) => (
                  <Button
                    key={t}
                    size="small"
                    variant={calType === t ? 'contained' : 'outlined'}
                    onClick={() => setCalType(t)}
                  >
                    {t}
                  </Button>
                ))}
              </Stack>

              <Stack spacing={2}>
                <TextField
                  label="Reference Fiducial / Marker Type"
                  size="small"
                  fullWidth
                  value={markerType}
                  onChange={(e) => setMarkerType(e.target.value)}
                />

                <Stack direction="row" spacing={1.5}>
                  <TextField
                    label="Known Marker Length (mm)"
                    type="number"
                    size="small"
                    fullWidth
                    value={knownMm}
                    onChange={(e) => setKnownMm(Number(e.target.value))}
                  />
                  <TextField
                    label="Measured Marker Length (px)"
                    type="number"
                    size="small"
                    fullWidth
                    value={measuredPx}
                    onChange={(e) => setMeasuredPx(Number(e.target.value))}
                  />
                </Stack>

                <Box
                  sx={{
                    p: 1.5,
                    borderRadius: 1.5,
                    backgroundColor: '#F0FDFA',
                    border: '1px solid #99F6E4',
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 700, color: '#0F766E', display: 'block' }}>
                    COMPUTED PHYSICAL SCALE FACTOR
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: '#123B50' }}>
                    {computedMmPerPx.toFixed(5)} mm / pixel
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Formula: mm_per_pixel = known_marker_length_mm ({knownMm}) / measured_marker_length_px ({measuredPx})
                  </Typography>
                </Box>

                <Stack direction="row" spacing={1.5}>
                  <TextField
                    label="Marker Anatomical Location"
                    size="small"
                    fullWidth
                    value={markerLocation}
                    onChange={(e) => setMarkerLocation(e.target.value)}
                  />
                  <TextField
                    label="Calibration Plane"
                    size="small"
                    fullWidth
                    value={calibrationPlane}
                    onChange={(e) => setCalibrationPlane(e.target.value)}
                  />
                </Stack>

                {calType === 'OPG' && (
                  <TextField
                    label="OPG Machine Magnification Factor (e.g., 1.20 = 20% magnification)"
                    type="number"
                    size="small"
                    fullWidth
                    value={magnificationFactor}
                    onChange={(e) => setMagnificationFactor(Number(e.target.value))}
                    helperText="OPG horizontal & vertical distances are divided by this magnification factor and adjusted by regional factors."
                  />
                )}

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={isPhysical}
                      onChange={(e) => setIsPhysical(e.target.checked)}
                    />
                  }
                  label={
                    <Typography variant="body2">
                      Marker is a verified physical reference scale (if unchecked, outputs are flagged <strong>Unscaled</strong>)
                    </Typography>
                  }
                />

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={samePlaneConfirmed}
                      onChange={(e) => setSamePlaneConfirmed(e.target.checked)}
                    />
                  }
                  label={
                    <Typography variant="body2">
                      Confirm reference marker lies in the same anatomical depth plane as the measured facial landmarks
                    </Typography>
                  }
                />

                <TextField
                  label="Calibration Notes"
                  size="small"
                  fullWidth
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />

                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<SaveIcon />}
                  disabled={saveCalMut.isPending}
                  onClick={() => saveCalMut.mutate()}
                >
                  Save Calibration & Recalculate Visit Measurements
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* Right Panel: Interactive Two-Point Ruler + Calibration History Table */}
        <Grid size={{ xs: 12, lg: 7 }}>
          <Stack spacing={2.5}>
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    Interactive Two-Point Fiducial Pixel Ruler ({calType})
                  </Typography>
                  <Chip
                    size="small"
                    color="secondary"
                    label={`Next Click Sets Point ${clickTarget} • Current Ruler: ${measuredPx} px`}
                  />
                </Stack>

                {!matchingImage ? (
                  <EmptyState title="No image available for this view" />
                ) : (
                  <Box
                    sx={{
                      backgroundColor: '#0F172A',
                      borderRadius: 2,
                      p: 1.5,
                      display: 'flex',
                      justifyContent: 'center',
                    }}
                  >
                    <svg
                      viewBox={`0 0 ${matchingImage.width || 800} ${matchingImage.height || 900}`}
                      style={{
                        width: '100%',
                        maxWidth: calType === 'OPG' ? 620 : 380,
                        height: 'auto',
                        cursor: 'crosshair',
                      }}
                      onClick={handleRulerSvgClick}
                    >
                      <image
                        href={withAuthTokenUrl(matchingImage.file_url)}
                        width={matchingImage.width || 800}
                        height={matchingImage.height || 900}
                      />
                      <line
                        x1={ptA.x}
                        y1={ptA.y}
                        x2={ptB.x}
                        y2={ptB.y}
                        stroke="#22D3EE"
                        strokeWidth={4}
                      />
                      <circle cx={ptA.x} cy={ptA.y} r={8} fill="#F59E0B" stroke="#FFF" strokeWidth={2} />
                      <circle cx={ptB.x} cy={ptB.y} r={8} fill="#10B981" stroke="#FFF" strokeWidth={2} />
                    </svg>
                  </Box>
                )}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Click Point A and Point B at the two ends of the embedded physical ruler on the image to automatically measure its pixel span.
                </Typography>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  Active Calibrations for Visit
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>View Type</TableCell>
                        <TableCell>Marker</TableCell>
                        <TableCell>Known (mm)</TableCell>
                        <TableCell>Measured (px)</TableCell>
                        <TableCell>mm / px</TableCell>
                        <TableCell>Physical?</TableCell>
                        <TableCell>Ver.</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(calibrationsQuery.data || []).map((c) => (
                        <TableRow key={c.id}>
                          <TableCell sx={{ fontWeight: 700 }}>{c.calibration_type}</TableCell>
                          <TableCell>{c.reference_marker_type}</TableCell>
                          <TableCell>{c.known_marker_length_mm} mm</TableCell>
                          <TableCell>{c.measured_marker_length_px} px</TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                            {c.mm_per_pixel.toFixed(5)}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={c.is_physical ? 'Pass' : 'Unscaled'} />
                          </TableCell>
                          <TableCell>v{c.version}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};
