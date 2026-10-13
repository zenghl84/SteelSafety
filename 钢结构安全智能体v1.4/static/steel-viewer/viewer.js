// Local Three.js modules are embedded into the iframe; no CDN is needed.
const data = JSON.parse(document.getElementById('steel-scene-data').textContent);
const modules = JSON.parse(document.getElementById('steel-module-data').textContent);
const root = document.getElementById('viewer');
const loading = document.getElementById('loading');
const blobURLs = [];
function moduleURL(source) {
  const url = URL.createObjectURL(new Blob([source], { type: 'text/javascript' }));
  blobURLs.push(url);
  return url;
}
const safe = value => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

async function init() {
  const meta = document.getElementById('model-meta');
  const multiplier = data.options.diameter_scale;
  const sectionCount = Object.keys(data.sections).length;
  meta.textContent = `${data.members.length} 根杆件 · ${sectionCount} 种截面 · 管径 ×${multiplier}`;
  root.dataset.memberCount = data.members.length;
  root.dataset.sensorCount = data.sensors.length;
  if (!data.members.length) {
    document.getElementById('empty').style.display = 'grid';
    loading.style.display = 'none';
    root.dataset.ready = 'true';
    return;
  }
  const core = moduleURL(modules['three.core.js']);
  const threeURL = moduleURL(modules['three.module.js'].replace(
    /(['"])\.\/three\.core\.js\1/g, JSON.stringify(core)));
  const remap = source => source.replace(/from\s*(['"])three\1/g, `from ${JSON.stringify(threeURL)}`);
  const [THREE, controlsModule, environmentModule] = await Promise.all([
    import(threeURL), import(moduleURL(remap(modules['OrbitControls.js']))),
    import(moduleURL(remap(modules['RoomEnvironment.js'])))
  ]);
  const canvasHost = document.getElementById('viewport');
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor('#ffffff', 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.setAttribute('aria-label', '按 MGT 截面渲染的立体钢管模型');
  canvasHost.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const positions = new Map(Object.entries(data.nodes).map(([id, xyz]) => [Number(id), new THREE.Vector3(...xyz)]));
  const bounds = new THREE.Box3().setFromPoints([...positions.values()]);
  const centre = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z, 1);
  scene.fog = new THREE.Fog('#ffffff', span * 2, span * 5);
  const environment = new environmentModule.RoomEnvironment();
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTexture = pmrem.fromScene(environment, .04).texture;
  scene.environment = envTexture;
  scene.environmentIntensity = .6;
  environment.dispose();
  pmrem.dispose();
  scene.add(new THREE.HemisphereLight('#f1f7ff', '#61788d', 1.1));
  const sunlight = new THREE.DirectionalLight('#fff8ed', 2.0);
  sunlight.position.copy(centre).add(new THREE.Vector3(span * .4, -span * .6, span * .95));
  sunlight.target.position.copy(centre);
  sunlight.castShadow = true;
  sunlight.shadow.mapSize.set(2048, 2048);
  Object.assign(sunlight.shadow.camera, { left: -span, right: span, top: span,
    bottom: -span, near: span * .1, far: span * 3.5 });
  sunlight.shadow.bias = -.00004;
  sunlight.shadow.normalBias = .04;
  scene.add(sunlight, sunlight.target);
  const fill = new THREE.DirectionalLight('#c5dfff', 1.0);
  fill.position.copy(centre).add(new THREE.Vector3(-span, span * .3, span * .4));
  scene.add(fill);
  const rim = new THREE.DirectionalLight('#ffffff', .8);
  rim.position.copy(centre).add(new THREE.Vector3(span * .2, span, span * .8));
  scene.add(rim);
  const floorZ = Math.min(bounds.min.z, 0) - .15;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(span * 8, span * 8),
    new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: .95, metalness: .0 }));
  floor.position.set(centre.x, centre.y, floorZ);
  floor.receiveShadow = true;
  scene.add(floor);
  const grid = new THREE.GridHelper(span * 1.45, 18, '#a7bbc9', '#a7bbc9');
  grid.rotation.x = Math.PI / 2;
  grid.position.set(centre.x, centre.y, floorZ + .006);
  grid.material.transparent = true;
  grid.material.opacity = .15;
  grid.material.depthWrite = false;
  scene.add(grid);

  const palette = ['#087e9b', '#4669cc', '#b45309', '#8054bc', '#16825d'];
  const colorby = data.options.colorby;
  const categories = [...new Set(data.members.map(e => colorby === '材料' ? e[3] : e[5]))]
    .sort((a, b) => String(a).localeCompare(String(b)));
  function memberColor(member) {
    if (colorby === '钢材质感') return new THREE.Color('#36546e');
    return new THREE.Color(palette[categories.indexOf(colorby === '材料' ? member[3] : member[5]) % palette.length]);
  }
  const legend = document.getElementById('legend');
  if (colorby === '钢材质感') {
    legend.innerHTML = '<span><i style="background:#36546e"></i>钢材质感</span><span><i style="background:#0e8298"></i>监测点</span>';
  } else {
    for (let i = 0; i < categories.length; i++) {
      const item = document.createElement('span');
      item.innerHTML = `<i style="background:${palette[i % palette.length]}"></i>${safe(colorby === '材料' ? data.materials[categories[i]] : categories[i])}`;
      legend.appendChild(item);
    }
  }
  const cylinder = new THREE.CylinderGeometry(1, 1, 1, 16, 1, false);
  const steel = new THREE.MeshStandardMaterial({ color: '#ffffff', metalness: .5,
    roughness: .34, envMapIntensity: .6 });
  const knownMembers = data.members.filter(e => data.sections[e[4]].diameter_m);
  const tubes = new THREE.InstancedMesh(cylinder, steel, knownMembers.length);
  tubes.castShadow = true;
  tubes.receiveShadow = true;
  const temp = new THREE.Object3D();
  const axis = new THREE.Vector3(0, 1, 0);
  const direction = new THREE.Vector3();
  const jointRadii = new Map();
  const memberByID = new Map(data.members.map(member => [member[0], member]));
  function setTubeTransform(object, member, scale = 1) {
    const a = positions.get(member[1]), b = positions.get(member[2]);
    direction.subVectors(b, a);
    const radius = data.sections[member[4]].diameter_m * multiplier * .5 * scale;
    object.position.copy(a).add(b).multiplyScalar(.5);
    object.quaternion.setFromUnitVectors(axis, direction.clone().normalize());
    object.scale.set(radius, direction.length(), radius);
    object.updateMatrix();
    return radius;
  }
  for (let i = 0; i < knownMembers.length; i++) {
    const member = knownMembers[i];
    const radius = setTubeTransform(temp, member);
    tubes.setMatrixAt(i, temp.matrix);
    tubes.setColorAt(i, memberColor(member));
    for (const node of [member[1], member[2]]) jointRadii.set(node, Math.max(jointRadii.get(node) || 0, radius));
  }
  tubes.instanceMatrix.needsUpdate = true;
  if (tubes.instanceColor) tubes.instanceColor.needsUpdate = true;
  tubes.computeBoundingSphere();
  scene.add(tubes);
  let joints;
  if (data.options.show_joints && jointRadii.size) {
    joints = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 12, 8),
      new THREE.MeshStandardMaterial({ color: '#57738a', roughness: .36, metalness: .5 }), jointRadii.size);
    let index = 0;
    for (const [id, radius] of jointRadii) {
      temp.position.copy(positions.get(id));
      temp.quaternion.identity();
      temp.scale.setScalar(radius * 1.3);
      temp.updateMatrix();
      joints.setMatrixAt(index++, temp.matrix);
    }
    joints.instanceMatrix.needsUpdate = true;
    joints.castShadow = true;
    joints.receiveShadow = true;
    joints.computeBoundingSphere();
    scene.add(joints);
  }
  // Unknown cross-sections are preserved as centre lines, without invented sizes.
  const missingCoordinates = [];
  for (const member of data.members) {
    if (data.sections[member[4]].diameter_m) continue;
    missingCoordinates.push(...positions.get(member[1]).toArray(), ...positions.get(member[2]).toArray());
  }
  if (missingCoordinates.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(missingCoordinates, 3));
    scene.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#53738e' })));
  }
  const selectedMesh = new THREE.Mesh(cylinder,
    new THREE.MeshStandardMaterial({ color: '#eaa359', metalness: .35, roughness: .28,
      emissive: '#b66316', emissiveIntensity: .22 }));
  selectedMesh.visible = false;
  scene.add(selectedMesh);
  const selectionBox = document.getElementById('selection');
  function highlight(id) {
    const member = memberByID.get(id);
    const section = member && data.sections[member[4]];
    selectedMesh.visible = !!section?.diameter_m;
    if (selectedMesh.visible) setTubeTransform(selectedMesh, member, 1.4);
    selectionBox.style.display = member ? 'block' : 'none';
    if (member) selectionBox.textContent = `单元 ${id} · ${section.name}`;
    requestRender();
  }
  const camera = new THREE.PerspectiveCamera(35, 1, .02, span * 20);
  camera.up.set(0, 0, 1);
  const controls = new controlsModule.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .1;
  controls.minDistance = span * .025;
  controls.maxDistance = span * 5;
  controls.maxPolarAngle = Math.PI * .495;
  controls.target.copy(centre);
  let userMoved = false;
  let currentView = 'perspective';
  const views = { perspective: new THREE.Vector3(1.1, 1.35, .82).normalize(),
    top: new THREE.Vector3(.001, -.001, 1).normalize(), front: new THREE.Vector3(1, 0, .02).normalize() };
  function fitCamera(view = currentView) {
    currentView = view;
    const direction = views[view];
    const right = new THREE.Vector3().crossVectors(camera.up, direction).normalize();
    const up = new THREE.Vector3().crossVectors(direction, right).normalize();
    const tanFov = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
    let distance = 0;
    for (const x of [bounds.min.x, bounds.max.x]) for (const y of [bounds.min.y, bounds.max.y]) for (const z of [bounds.min.z, bounds.max.z]) {
      const offset = new THREE.Vector3(x, y, z).sub(centre);
      const depth = offset.dot(direction);
      distance = Math.max(distance, depth + Math.abs(offset.dot(right)) / (tanFov * camera.aspect),
        depth + Math.abs(offset.dot(up)) / tanFov);
    }
    controls.target.copy(centre);
    camera.position.copy(centre).addScaledVector(direction, distance * 1.08);
    camera.lookAt(centre);
    controls.update();
    for (const button of document.querySelectorAll('[data-view]')) button.classList.toggle('active', button.dataset.view === view);
    requestRender();
  }
  const sensorLayer = document.getElementById('sensor-layer');
  const tooltip = document.getElementById('tooltip');
  function showTooltip(html, x, y) {
    tooltip.innerHTML = html;
    tooltip.style.display = 'block';
    tooltip.style.left = Math.max(10, Math.min(x + 15, root.clientWidth - tooltip.offsetWidth - 12)) + 'px';
    tooltip.style.top = Math.max(62, Math.min(y + 15, root.clientHeight - tooltip.offsetHeight - 15)) + 'px';
  }
  const pins = data.sensors.map(sensor => {
    const button = document.createElement('button');
    button.className = 'sensor-pin';
    button.setAttribute('aria-label', `测点 ${sensor.label}`);
    button.innerHTML = `<span>${safe(sensor.label)}</span>`;
    button.addEventListener('pointermove', event => {
      const rect = root.getBoundingClientRect();
      showTooltip(sensor.detail, event.clientX - rect.left, event.clientY - rect.top);
    });
    button.addEventListener('pointerleave', () => { tooltip.style.display = 'none'; });
    button.addEventListener('focus', () => showTooltip(sensor.detail, parseFloat(button.style.left), parseFloat(button.style.top)));
    button.addEventListener('blur', () => { tooltip.style.display = 'none'; });
    sensorLayer.appendChild(button);
    return { button, position: new THREE.Vector3(...sensor.position) };
  });
  let renderPending = false;
  let rendered = false;
  function requestRender() {
    if (renderPending) return;
    renderPending = true;
    requestAnimationFrame(() => {
      renderPending = false;
      if (!root.clientWidth) return;
      controls.update();
      renderer.render(scene, camera);
      for (const pin of pins) {
        const projected = pin.position.clone().project(camera);
        pin.button.style.display = Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1 && projected.z < 1 ? 'block' : 'none';
        pin.button.style.left = (projected.x * .5 + .5) * root.clientWidth + 'px';
        pin.button.style.top = (-projected.y * .5 + .5) * root.clientHeight + 'px';
      }
      if (!rendered) {
        rendered = true;
        renderer.shadowMap.autoUpdate = false;
        loading.style.display = 'none';
        root.dataset.ready = 'true';
        root.dataset.triangles = renderer.info.render.triangles;
        root.dataset.drawCalls = renderer.info.render.calls;
      }
    });
  }
  controls.addEventListener('change', requestRender);
  controls.addEventListener('start', () => { userMoved = true; tooltip.style.display = 'none'; });
  const resize = new ResizeObserver(() => {
    const width = root.clientWidth, height = root.clientHeight;
    if (!width) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (!userMoved) fitCamera();
    requestRender();
  });
  resize.observe(root);
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let pressed = false, lastPick = 0, pointerStart = null;
  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObject(tubes, false)[0];
    return hit ? knownMembers[hit.instanceId] : null;
  }
  renderer.domElement.addEventListener('pointerdown', event => { pressed = true; pointerStart = [event.clientX, event.clientY]; });
  window.addEventListener('pointerup', event => {
    const wasPressed = pressed;
    pressed = false;
    if (!wasPressed || event.button !== 0 || !pointerStart || Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) > 4) return;
    const member = pick(event);
    highlight(member ? member[0] : data.selected);
  });
  renderer.domElement.addEventListener('pointermove', event => {
    if (pressed || performance.now() - lastPick < 120) return;
    lastPick = performance.now();
    const member = pick(event);
    if (!member) { tooltip.style.display = 'none'; return; }
    const section = data.sections[member[4]];
    const length = positions.get(member[1]).distanceTo(positions.get(member[2]));
    const wall = section.wall_m ? `<br>壁厚：${(section.wall_m * 1000).toFixed(2).replace(/\.?0+$/, '')} mm` : '';
    const html = `<b>单元 ${member[0]}</b><br>截面：${safe(section.name)}<br>外径：${(section.diameter_m * 1000).toFixed(1)} mm${wall}<br>材料：${safe(data.materials[member[3]])}<br>长度：${length.toFixed(3)} m<br>点击高亮杆件`;
    const rect = root.getBoundingClientRect();
    showTooltip(html, event.clientX - rect.left, event.clientY - rect.top);
  });
  renderer.domElement.addEventListener('pointerleave', () => { tooltip.style.display = 'none'; });
  for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => { userMoved = false; fitCamera(button.dataset.view); });
  document.getElementById('reset').addEventListener('click', () => { userMoved = false; fitCamera('perspective'); highlight(data.selected); });
  document.getElementById('export').addEventListener('click', () => {
    const width = renderer.domElement.width, height = renderer.domElement.height;
    const scale = width / root.clientWidth;
    const exported = document.createElement('canvas');
    exported.width = width;
    exported.height = height;
    const context = exported.getContext('2d');
    const background = context.createLinearGradient(0, 0, width, height);
    background.addColorStop(0, '#ffffff');
    background.addColorStop(1, '#ffffff');
    context.fillStyle = background;
    context.fillRect(0, 0, width, height);
    context.drawImage(renderer.domElement, 0, 0, width, height);
    for (const sensor of data.sensors) {
      const point = new THREE.Vector3(...sensor.position).project(camera);
      if (Math.abs(point.x) > 1 || Math.abs(point.y) > 1 || point.z >= 1) continue;
      const x = (point.x * .5 + .5) * width, y = (-point.y * .5 + .5) * height;
      context.beginPath();
      context.arc(x, y, 6 * scale, 0, Math.PI * 2);
      context.fillStyle = '#0e8298';
      context.fill();
      context.lineWidth = 2.5 * scale;
      context.strokeStyle = '#ffffff';
      context.stroke();
      context.font = `600 ${11 * scale}px "Times New Roman", serif`;
      const textWidth = context.measureText(sensor.label).width;
      context.fillStyle = '#fffffff0';
      context.fillRect(x - textWidth / 2 - 5 * scale, y - 31 * scale, textWidth + 10 * scale, 17 * scale);
      context.fillStyle = '#15536e';
      context.textAlign = 'center';
      context.fillText(sensor.label, x, y - 18 * scale);
    }
    context.textAlign = 'left';
    context.fillStyle = '#263c53';
    context.font = `600 ${16 * scale}px "Microsoft YaHei", serif`;
    context.fillText('三维钢结构模型', 18 * scale, 31 * scale);
    context.font = `${11 * scale}px "Microsoft YaHei", serif`;
    context.fillStyle = '#52657f';
    context.fillText(meta.textContent, 18 * scale, 51 * scale);
    context.fillText('钢管外形按 MGT 截面显示；节点球为连接位置示意。', 18 * scale, height - 18 * scale);
    const image = exported.toDataURL('image/png');
    document.getElementById('export-image').src = image;
    document.getElementById('save-image').href = image;
    document.getElementById('export-preview').hidden = false;
  });
  document.getElementById('close-preview').addEventListener('click', () => {
    document.getElementById('export-preview').hidden = true;
  });
  window.addEventListener('pagehide', () => {
    resize.disconnect();
    controls.dispose();
    scene.traverse(object => { object.geometry?.dispose(); if (object.material) object.material.dispose(); });
    envTexture.dispose();
    renderer.dispose();
    for (const url of blobURLs) URL.revokeObjectURL(url);
  });
  renderer.setSize(Math.max(root.clientWidth, 1), root.clientHeight);
  camera.aspect = Math.max(root.clientWidth, 1) / root.clientHeight;
  camera.updateProjectionMatrix();
  fitCamera('perspective');
  highlight(data.selected);
  requestRender();
}
init().catch(error => {
  loading.textContent = '实体模型加载失败，请切换侧栏中的“线框模型”继续查看。';
  root.dataset.error = error.message;
  console.error('Steel viewer:', error);
});
