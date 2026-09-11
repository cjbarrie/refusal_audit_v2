'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, ChevronDown, CircleHelp, Info, Layers3, LocateFixed, MousePointer2, RotateCcw, Search, X } from 'lucide-react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

type PromptPoint = {
  prompt_id: string; prompt_text: string; issue_id: string; domain: string;
  region_focus: string; tier: string; route: string; prompt_origin_language: string;
  umap_x: number; umap_y: number; umap_3d_x: number; umap_3d_y: number; umap_3d_z: number;
};

type Refusal = {
  prompt_id: string; prompt_language: string; model: string; developer_jurisdiction: string;
  prompt_text: string; prompt_text_en: string; response_text: string; topic_domain: string;
  region_focus: string; controversy_tier: string; route: string; position_side: string;
  task_behavior: string; substantive_refusal: string; stance_disclaimer: boolean;
  epistemic_limitation: boolean; language_fidelity: string; output_quality: string;
  technical_failure: string; confidence: string; refusal_evidence_span: string | null;
  annotation_source: string;
};

type Metadata = {
  canonical_release: string;
  counts: { prompts: number; responses: number; genuine_refusals: number; models: number; languages: number };
};
type Filters = { jurisdiction: string; model: string; language: string; domain: string };

const ALL = 'All';
const LANGUAGE_NAMES: Record<string, string> = { en: 'English', zh: 'Chinese', ar: 'Arabic', ru: 'Russian', hi: 'Hindi' };
const JURISDICTION_COLOURS: Record<string, string> = {
  CN: '#ff665f', EU: '#6fc4ff', India: '#f3b254', MENA: '#bd8aff', US: '#55d9b3',
};

async function loadJson<T>(path: string, errorMessage: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(errorMessage);
  return response.json() as Promise<T>;
}

function unique(values: string[]) {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function titleCase(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function SelectControl({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (value: string) => void;
}) {
  return (
    <label className="filter-control">
      <span>{label}</span>
      <span className="select-wrap">
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          <option value={ALL}>{ALL}</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {label === 'Language' ? LANGUAGE_NAMES[option] ?? option : titleCase(option)}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden="true" size={13} />
      </span>
    </label>
  );
}

function normalise(values: number[]) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const centre = (min + max) / 2;
  const span = Math.max(max - min, 0.001);
  return values.map((value) => ((value - centre) / span) * 9);
}

function Constellation({ prompts, refusalCounts, accentJurisdiction, selectedId, dimension, onHover, onSelect, resetToken }: {
  prompts: PromptPoint[];
  refusalCounts: Map<string, number>;
  accentJurisdiction: string | null;
  selectedId: string | null;
  dimension: '3D' | '2D';
  onHover: (point: PromptPoint | null, x?: number, y?: number) => void;
  onSelect: (point: PromptPoint) => void;
  resetToken: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef<{ camera: THREE.PerspectiveCamera; controls: OrbitControls } | null>(null);

  const positions = useMemo(() => {
    const xs = normalise(prompts.map((point) => dimension === '3D' ? point.umap_3d_x : point.umap_x));
    const ys = normalise(prompts.map((point) => dimension === '3D' ? point.umap_3d_y : point.umap_y));
    const zs = dimension === '3D'
      ? normalise(prompts.map((point) => point.umap_3d_z)).map((value) => value * 0.72)
      : prompts.map(() => 0);
    return prompts.map((_, index) => new THREE.Vector3(xs[index], ys[index], zs[index]));
  }, [dimension, prompts]);

  useEffect(() => {
    if (!host.current || prompts.length === 0) return;
    const container = host.current;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2('#05070b', 0.032);
    const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 100);
    camera.position.set(0, 0.4, 15.5);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor('#05070b', 1);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;
    controls.minDistance = 5;
    controls.maxDistance = 28;
    controls.rotateSpeed = 0.42;
    controls.zoomSpeed = 0.65;
    controls.panSpeed = 0.55;
    controls.autoRotate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches && dimension === '3D';
    controls.autoRotateSpeed = 0.18;
    const stopDrift = () => { controls.autoRotate = false; };
    controls.addEventListener('start', stopDrift);

    const backgroundGeometry = new THREE.BufferGeometry().setFromPoints(positions);
    const backgroundColours = new Float32Array(prompts.length * 3);
    prompts.forEach((point, index) => {
      new THREE.Color(point.prompt_id === selectedId ? '#fff4df' : '#8995a8').toArray(backgroundColours, index * 3);
    });
    backgroundGeometry.setAttribute('color', new THREE.BufferAttribute(backgroundColours, 3));
    const backgroundMaterial = new THREE.PointsMaterial({
      size: 0.055, sizeAttenuation: true, transparent: true, opacity: 0.42,
      vertexColors: true, depthWrite: false,
    });
    const background = new THREE.Points(backgroundGeometry, backgroundMaterial);
    scene.add(background);

    const activeIndices: number[] = [];
    const activePositions: THREE.Vector3[] = [];
    const activeColours: number[] = [];
    let maximum = 1;
    refusalCounts.forEach((value) => { maximum = Math.max(maximum, value); });
    prompts.forEach((point, index) => {
      const count = refusalCounts.get(point.prompt_id) ?? 0;
      if (!count) return;
      activeIndices.push(index);
      activePositions.push(positions[index]);
      const colour = new THREE.Color(
        accentJurisdiction ? JURISDICTION_COLOURS[accentJurisdiction] : '#ff4f5f',
      );
      colour.multiplyScalar(0.62 + 0.38 * Math.sqrt(count / maximum));
      activeColours.push(colour.r, colour.g, colour.b);
    });

    const activeGeometry = new THREE.BufferGeometry().setFromPoints(activePositions);
    activeGeometry.setAttribute('color', new THREE.Float32BufferAttribute(activeColours, 3));
    const glowMaterial = new THREE.PointsMaterial({
      size: 0.22, sizeAttenuation: true, transparent: true, opacity: 0.1,
      vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const activeMaterial = new THREE.PointsMaterial({
      size: 0.095, sizeAttenuation: true, transparent: true, opacity: 0.98,
      vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const glow = new THREE.Points(activeGeometry, glowMaterial);
    const active = new THREE.Points(activeGeometry, activeMaterial);
    scene.add(glow, active);

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 0.11 };
    const mouse = new THREE.Vector2();
    const pointAt = (event: PointerEvent | MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const activeHits = raycaster.intersectObject(active, false);
      const contextHits = activeHits.length ? [] : raycaster.intersectObject(background, false);
      const hit = activeHits[0] ?? contextHits[0];
      if (!hit || hit.index === undefined) return null;
      return prompts[activeHits.length ? activeIndices[hit.index] : hit.index];
    };
    const pointerMove = (event: PointerEvent) => {
      const point = pointAt(event);
      renderer.domElement.style.cursor = point ? 'pointer' : 'grab';
      onHover(point, event.clientX, event.clientY);
    };
    const pointerLeave = () => onHover(null);
    const click = (event: MouseEvent) => {
      const point = pointAt(event);
      if (point) onSelect(point);
      controls.autoRotate = false;
    };
    renderer.domElement.addEventListener('pointermove', pointerMove);
    renderer.domElement.addEventListener('pointerleave', pointerLeave);
    renderer.domElement.addEventListener('click', click);

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    let frame = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();
    state.current = { camera, controls };

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.removeEventListener('start', stopDrift);
      controls.dispose();
      renderer.domElement.removeEventListener('pointermove', pointerMove);
      renderer.domElement.removeEventListener('pointerleave', pointerLeave);
      renderer.domElement.removeEventListener('click', click);
      backgroundGeometry.dispose(); backgroundMaterial.dispose(); activeGeometry.dispose();
      glowMaterial.dispose(); activeMaterial.dispose(); renderer.dispose(); renderer.domElement.remove();
      state.current = null;
    };
  }, [accentJurisdiction, dimension, onHover, onSelect, positions, prompts, refusalCounts, selectedId]);

  useEffect(() => {
    if (!state.current) return;
    state.current.camera.position.set(0, 0.4, 15.5);
    state.current.controls.target.set(0, 0, 0);
    state.current.controls.update();
  }, [resetToken]);

  return <div ref={host} className="constellation-canvas" aria-label="Interactive semantic constellation" />;
}

export function RefusalObservatory() {
  const [prompts, setPrompts] = useState<PromptPoint[]>([]);
  const [refusals, setRefusals] = useState<Refusal[]>([]);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({ jurisdiction: ALL, model: ALL, language: ALL, domain: ALL });
  const [search, setSearch] = useState('');
  const [dimension, setDimension] = useState<'3D' | '2D'>('3D');
  const [hovered, setHovered] = useState<{ point: PromptPoint; x: number; y: number } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedResponse, setSelectedResponse] = useState(0);
  const [showMethods, setShowMethods] = useState(false);
  const [resetToken, setResetToken] = useState(0);

  useEffect(() => {
    Promise.all([
      loadJson<PromptPoint[]>('./data/prompts.json', 'Prompt data could not be loaded.'),
      loadJson<Refusal[]>('./data/refusals.json', 'Refusal data could not be loaded.'),
      loadJson<Metadata>('./data/metadata.json', 'Metadata could not be loaded.'),
    ]).then(([promptData, refusalData, metadataData]) => {
      setPrompts(promptData); setRefusals(refusalData); setMetadata(metadataData);
    }).catch((error: Error) => setLoadingError(error.message));
  }, []);

  const filteredRefusals = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return refusals.filter((row) => {
      if (filters.jurisdiction !== ALL && row.developer_jurisdiction !== filters.jurisdiction) return false;
      if (filters.model !== ALL && row.model !== filters.model) return false;
      if (filters.language !== ALL && row.prompt_language !== filters.language) return false;
      if (filters.domain !== ALL && row.topic_domain !== filters.domain) return false;
      if (needle && !`${row.prompt_text_en} ${row.prompt_text} ${row.response_text}`.toLocaleLowerCase().includes(needle)) return false;
      return true;
    });
  }, [filters, refusals, search]);

  const refusalCounts = useMemo(() => {
    const counts = new Map<string, number>();
    filteredRefusals.forEach((row) => counts.set(row.prompt_id, (counts.get(row.prompt_id) ?? 0) + 1));
    return counts;
  }, [filteredRefusals]);

  const selectedPoint = prompts.find((point) => point.prompt_id === selectedId) ?? null;
  const selectedRefusals = selectedId ? filteredRefusals.filter((row) => row.prompt_id === selectedId) : [];
  const detail = selectedRefusals[selectedResponse] ?? selectedRefusals[0] ?? null;
  const models = unique(refusals.map((row) => row.model));
  const jurisdictions = unique(refusals.map((row) => row.developer_jurisdiction));
  const languages = unique(refusals.map((row) => row.prompt_language));
  const domains = unique(refusals.map((row) => row.topic_domain));

  const onHover = useCallback((point: PromptPoint | null, x = 0, y = 0) => {
    setHovered(point ? { point, x, y } : null);
  }, []);
  const onSelect = useCallback((point: PromptPoint) => {
    setSelectedId(point.prompt_id); setSelectedResponse(0);
  }, []);

  const filterSummary = [
    filters.language === ALL ? 'All languages' : LANGUAGE_NAMES[filters.language],
    filters.model === ALL ? (filters.jurisdiction === ALL ? 'All models' : `${filters.jurisdiction} models`) : titleCase(filters.model),
  ].join(' · ');

  const reset = () => {
    setFilters({ jurisdiction: ALL, model: ALL, language: ALL, domain: ALL });
    setSearch(''); setSelectedId(null); setSelectedResponse(0); setResetToken((value) => value + 1);
  };

  const setFilter = (key: keyof Filters, value: string) => {
    setFilters((current) => {
      if (key === 'jurisdiction' && value !== ALL) return { ...current, jurisdiction: value, model: ALL };
      if (key === 'model' && value !== ALL) {
        const jurisdiction = refusals.find((row) => row.model === value)?.developer_jurisdiction ?? ALL;
        return { ...current, model: value, jurisdiction };
      }
      return { ...current, [key]: value };
    });
    setSelectedResponse(0);
  };

  if (loadingError) {
    return <main className="load-state"><p>Refusal Observatory</p><h1>The local data could not be loaded.</h1><span>{loadingError} Rebuild the browser assets and reload.</span></main>;
  }
  if (!metadata || prompts.length === 0) {
    return <main className="load-state loading"><div className="loader-orbit" /><p>Mapping semantic space</p></main>;
  }

  return (
    <main className="observatory-shell">
      <Constellation prompts={prompts} refusalCounts={refusalCounts}
        accentJurisdiction={filters.jurisdiction === ALL ? null : filters.jurisdiction}
        selectedId={selectedId} dimension={dimension} resetToken={resetToken} onHover={onHover} onSelect={onSelect} />

      <header className="observatory-header">
        <div className="brand-lockup"><span className="brand-mark"><span /></span><div><p>Refusal Observatory</p><span>Semantic atlas of model non-compliance</span></div></div>
        <div className="header-actions"><button className="quiet-button" onClick={() => setShowMethods(true)}><CircleHelp size={15} /> How to read this</button><span className="release-pill">{metadata.canonical_release}</span></div>
      </header>

      <section className="view-summary" aria-live="polite"><p>{filterSummary}</p><strong>{filteredRefusals.length.toLocaleString()} genuine refusals</strong><span>across {refusalCounts.size.toLocaleString()} of {metadata.counts.prompts.toLocaleString()} prompts</span></section>

      <section className="filter-dock" aria-label="Filter the refusal constellation">
        <div className="search-control"><Search size={14} aria-hidden="true" /><input aria-label="Search prompts and refusal responses" placeholder="Search prompts or responses" value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button aria-label="Clear search" onClick={() => setSearch('')}><X size={13} /></button>}</div>
        <div className="filter-divider" />
        <SelectControl label="Jurisdiction" value={filters.jurisdiction} options={jurisdictions} onChange={(value) => setFilter('jurisdiction', value)} />
        <SelectControl label="Model" value={filters.model} options={models.filter((model) => filters.jurisdiction === ALL || refusals.some((row) => row.model === model && row.developer_jurisdiction === filters.jurisdiction))} onChange={(value) => setFilter('model', value)} />
        <SelectControl label="Language" value={filters.language} options={languages} onChange={(value) => setFilter('language', value)} />
        <SelectControl label="Domain" value={filters.domain} options={domains} onChange={(value) => setFilter('domain', value)} />
        <div className="filter-divider" />
        <div className="dimension-toggle" aria-label="Projection mode"><button className={dimension === '3D' ? 'active' : ''} onClick={() => setDimension('3D')}><Box size={13} /> 3D</button><button className={dimension === '2D' ? 'active' : ''} onClick={() => setDimension('2D')}><Layers3 size={13} /> 2D</button></div>
        <button className="icon-button" aria-label="Reset filters and view" onClick={reset}><RotateCcw size={15} /></button>
      </section>

      <div className="map-key"><span><i className="key-dot context" /> Context</span><span><i className="key-dot refusal" style={filters.jurisdiction === ALL ? undefined : { background: JURISDICTION_COLOURS[filters.jurisdiction], boxShadow: `0 0 10px ${JURISDICTION_COLOURS[filters.jurisdiction]}` }} /> Genuine refusal</span><em>drag to rotate · scroll to zoom · select a star</em></div>

      {hovered && <div className="star-tooltip" style={{ left: Math.min(hovered.x + 16, window.innerWidth - 340), top: Math.min(hovered.y + 16, window.innerHeight - 150) }}><span>{titleCase(hovered.point.domain)} · {hovered.point.region_focus}</span><p>{hovered.point.prompt_text}</p><strong>{refusalCounts.get(hovered.point.prompt_id) ?? 0} matching refusal{(refusalCounts.get(hovered.point.prompt_id) ?? 0) === 1 ? '' : 's'}</strong></div>}

      <aside className={`detail-drawer ${selectedPoint ? 'open' : ''}`} aria-hidden={!selectedPoint}>
        {selectedPoint && <><div className="drawer-topline"><span><LocateFixed size={14} /> Prompt {selectedPoint.prompt_id.slice(0, 8)}</span><button aria-label="Close prompt details" onClick={() => setSelectedId(null)}><X size={18} /></button></div><div className="drawer-scroll">
          <div className="prompt-heading"><p>{titleCase(selectedPoint.domain)} · {selectedPoint.region_focus} · {titleCase(selectedPoint.tier)}</p><h2>{selectedPoint.prompt_text}</h2></div>
          <div className="drawer-metrics"><div><strong>{selectedRefusals.length}</strong><span>matching refusals</span></div><div><strong>{unique(selectedRefusals.map((row) => row.model)).length}</strong><span>models</span></div><div><strong>{unique(selectedRefusals.map((row) => row.prompt_language)).length}</strong><span>languages</span></div></div>
          {selectedRefusals.length === 0 ? <div className="empty-detail"><MousePointer2 size={20} /><p>No genuine refusal matches the current filters for this prompt.</p></div> : <>
            <label className="response-picker"><span>Inspect response</span><select value={selectedResponse} onChange={(event) => setSelectedResponse(Number(event.target.value))}>{selectedRefusals.map((row, index) => <option key={`${row.model}-${row.prompt_language}`} value={index}>{titleCase(row.model)} · {LANGUAGE_NAMES[row.prompt_language] ?? row.prompt_language} · {titleCase(row.substantive_refusal)}</option>)}</select></label>
            {detail && <article className="response-record"><div className="record-tags"><span style={{ '--tag-colour': JURISDICTION_COLOURS[detail.developer_jurisdiction] } as React.CSSProperties}>{detail.developer_jurisdiction}</span><span>{LANGUAGE_NAMES[detail.prompt_language] ?? detail.prompt_language}</span><span>{titleCase(detail.substantive_refusal)}</span></div>
              {detail.prompt_language !== 'en' && <section><h3>Delivered prompt</h3><p dir={detail.prompt_language === 'ar' ? 'rtl' : 'auto'}>{detail.prompt_text}</p></section>}
              <section><h3>Model response</h3><p className="model-response" dir={detail.prompt_language === 'ar' ? 'rtl' : 'auto'}>{detail.response_text}</p></section>
              {detail.refusal_evidence_span && <section className="evidence-block"><h3>Refusal evidence</h3><blockquote>{detail.refusal_evidence_span}</blockquote></section>}
              <dl className="coding-grid"><div><dt>Task behaviour</dt><dd>{titleCase(detail.task_behavior)}</dd></div><div><dt>Response quality</dt><dd>{titleCase(detail.output_quality)}</dd></div><div><dt>Language fidelity</dt><dd>{titleCase(detail.language_fidelity)}</dd></div><div><dt>Confidence</dt><dd>{titleCase(detail.confidence)}</dd></div></dl>
            </article>}
          </>}
        </div></>}
      </aside>

      {showMethods && <div className="modal-scrim"><button className="modal-backdrop" aria-label="Close reading guide" onClick={() => setShowMethods(false)} /><dialog open className="methods-card" aria-labelledby="methods-title"><button className="modal-close" aria-label="Close" onClick={() => setShowMethods(false)}><X size={18} /></button><span className="eyebrow"><Info size={13} /> Reading the map</span><h2 id="methods-title">Nearby prompts have similar meanings.</h2><p>Each star is one English prompt meaning. The same coordinates are reused for every model and language, so filtering changes only which refusals are illuminated—not the map itself.</p><div className="method-rule" /><p><strong>Bright stars</strong> mark prompts with at least one genuine refusal in the selected slice. The pooled view uses crimson; selecting a jurisdiction or model switches to that jurisdiction&apos;s accent colour.</p><p><strong>Dim stars</strong> provide semantic context and remain selectable even when no refusal matches.</p><p className="method-note">The three-dimensional UMAP is an exploratory locator fitted once to 512-dimensional English-prompt embeddings. Axes, orientation and long distances have no substantive meaning. Use 2D mode for direct continuity with the paper figures.</p><footer>{metadata.counts.prompts.toLocaleString()} prompts · {metadata.counts.models} models · {metadata.counts.languages} languages · {metadata.canonical_release}</footer></dialog></div>}
    </main>
  );
}
