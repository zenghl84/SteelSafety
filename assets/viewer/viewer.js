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
  const [THREE, controlsModule, environmentModule, siteModule] = await Promise.all([
    import(threeURL), import(moduleURL(remap(modules['OrbitControls.js']))),
    import(moduleURL(remap(modules['RoomEnvironment.js']))),
    import(moduleURL(modules['SiteEnvironment.js']))
  ]);
  const canvasHost = document.getElementById('viewport');
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor('#e5f1fa', 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .83;
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
  scene.fog = new THREE.Fog('#e5f1fa', span * 1.7, span * 8);
  const environment = new environmentModule.RoomEnvironment();
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTexture = pmrem.fromScene(environment, .04).texture;
  scene.environment = envTexture;
  scene.environmentIntensity = .6;
  environment.dispose();
  pmrem.dispose();
  scene.add(new THREE.HemisphereLight('#f1f7ff', '#61788d', 1.1));
  const sunlight = new THREE.DirectionalLight('#fff8ed', 2.7);
  sunlight.position.copy(centre).add(new THREE.Vector3(span * .4, -span * .6, span * .95));
  sunlight.target.position.copy(centre);
  sunlight.castShadow = true;
  sunlight.shadow.mapSize.set(2048, 2048);
  Object.assign(sunlight.shadow.camera, { left: -span, right: span, top: span,
    bottom: -span, near: span * .1, far: span * 3.5 });
  sunlight.shadow.bias = -.00004;
  sunlight.shadow.normalBias = .04;
  scene.add(sunlight, sunlight.target);
  const fill = new THREE.DirectionalLight('#c5dfff', .55);
  fill.position.copy(centre).add(new THREE.Vector3(-span, span * .3, span * .4));
  scene.add(fill);
  const rim = new THREE.DirectionalLight('#ffffff', .4);
  rim.position.copy(centre).add(new THREE.Vector3(span * .2, span, span * .8));
  scene.add(rim);
  const floorZ = Math.min(bounds.min.z, 0) - .15;
  const site = siteModule.createSiteEnvironment(THREE, { bounds, centre, size, span, floorZ });
  scene.add(site.group);
  root.dataset.environment = site.group.userData.kind;
  root.dataset.vegetationCount = site.group.userData.vegetationCount;

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
  let missingLines;
  if (missingCoordinates.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(missingCoordinates, 3));
    missingLines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#53738e' }));
    scene.add(missingLines);
  }
  const selectedMesh = new THREE.Mesh(cylinder,
    new THREE.MeshStandardMaterial({ color: '#eaa359', metalness: .35, roughness: .28,
      emissive: '#b66316', emissiveIntensity: .22 }));
  selectedMesh.visible = false;
  scene.add(selectedMesh);
  const selectionBox = document.getElementById('selection');
  let selectedID = 0;
  function highlight(id) {
    selectedID = memberByID.has(id) ? id : 0;
    const member = memberByID.get(id);
    const section = member && data.sections[member[4]];
    selectedMesh.visible = !!section?.diameter_m;
    if (selectedMesh.visible) setTubeTransform(selectedMesh, member, 1.4);
    selectionBox.style.display = member ? 'block' : 'none';
    if (member) selectionBox.textContent = `单元 ${id} · ${section.name}` + stressText(id);
    root.dataset.selectedId = String(selectedID);
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
  let toolMode = 'rotate', clipEnabled = false, transparent = false, riskEnabled = false;
  let clipAxis = 'X', clipPosition = 50, riskValues = {};
  const hiddenMembers = new Map();
  const clipPlane = new THREE.Plane(new THREE.Vector3(1, 0, 0), -centre.x);
  renderer.localClippingEnabled = true;
  function notify(text) { parent.postMessage({type:'platform-notice',text}, '*'); }
  function setTool(mode) {
    toolMode = mode;
    controls.enableRotate = mode === 'rotate';
    controls.enablePan = mode === 'rotate' || mode === 'pan';
    controls.mouseButtons.LEFT = mode === 'rotate' ? THREE.MOUSE.ROTATE : mode === 'pan' ? THREE.MOUSE.PAN : mode === 'zoom' ? THREE.MOUSE.DOLLY : null;
    renderer.domElement.style.cursor = mode === 'pan' ? 'grab' : mode === 'zoom' ? 'ns-resize' : mode === 'select' || mode === 'hide' ? 'crosshair' : 'default';
    root.dataset.tool = mode;
  }
  function setClip(enabled, axis = clipAxis, position = clipPosition) {
    clipEnabled = enabled; clipAxis = ['X','Y','Z'].includes(axis) ? axis : 'X';
    clipPosition = Math.max(0, Math.min(100, Number(position) || 0));
    const component = clipAxis.toLowerCase();
    clipPlane.normal.set(component==='x'?1:0,component==='y'?1:0,component==='z'?1:0);
    clipPlane.constant = -(bounds.min[component] + (bounds.max[component]-bounds.min[component])*clipPosition/100);
    for (const object of [tubes,joints,missingLines,selectedMesh]) if (object?.material) {
      object.material.clippingPlanes = enabled ? [clipPlane] : [];
      object.material.clipShadows = true;
      object.material.needsUpdate = true;
    }
    root.dataset.clipping = String(enabled);
    root.dataset.clipPosition = String(clipPosition);
    renderer.shadowMap.needsUpdate = true;
    requestRender();
  }
  function setTransparent(enabled) {
    transparent = enabled;
    for (const object of [tubes,joints,missingLines]) if(object?.material) {
      object.material.transparent = enabled;
      object.material.opacity = enabled ? .26 : 1;
      object.material.depthWrite = !enabled;
      object.material.needsUpdate = true;
    }
    root.dataset.transparent = String(enabled);
    requestRender();
  }
  function stressText(id) {
    const r=data.stress?.records[String(id)];
    return r ? ` · CS19 组合正应力绝对值最大 ${r.abs_mpa} MPa（I端 ${r.I.abs_mpa} / J端 ${r.J.abs_mpa}）` : ' · CS19无应力结果';
  }
  const stressMaterial = new THREE.MeshBasicMaterial({color:'#ffffff',toneMapped:false});
  function stressColor(value) {
    const stops=[0,7.7,14.7,26.3,46.1,203];
    const colors=['#003cff','#00c8ff','#00d56a','#ffe000','#ff8900','#ff1800'];
    const mpa=Math.max(0,Math.min(203,value*203));
    let k=0;while(k<4 && mpa>stops[k+1])k++;
    return new THREE.Color(colors[k]).lerp(new THREE.Color(colors[k+1]),(mpa-stops[k])/(stops[k+1]-stops[k]));
  }
  const endpointI=new Float32Array(knownMembers.length*3),endpointJ=new Float32Array(knownMembers.length*3);
  knownMembers.forEach((member,i)=>{
    const r=data.stress?.records[String(member[0])];
    (r ? stressColor(r.I.abs_mpa/203) : new THREE.Color('#929da8')).toArray(endpointI,i*3);
    (r ? stressColor(r.J.abs_mpa/203) : new THREE.Color('#929da8')).toArray(endpointJ,i*3);
  });
  tubes.geometry.setAttribute('stressI',new THREE.InstancedBufferAttribute(endpointI,3));
  tubes.geometry.setAttribute('stressJ',new THREE.InstancedBufferAttribute(endpointJ,3));
  stressMaterial.onBeforeCompile=shader=>{
    shader.vertexShader='attribute vec3 stressI;\nattribute vec3 stressJ;\nvarying vec3 smoothStress;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nsmoothStress=mix(stressI,stressJ,clamp(position.y+0.5,0.0,1.0));');
    shader.fragmentShader='varying vec3 smoothStress;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\ndiffuseColor.rgb=smoothStress;');
  };
  function setRisk(enabled, values = riskValues) {
    const target=enabled ? stressMaterial : steel;
    if(tubes.material!==target){
      const previous=tubes.material;
      target.clippingPlanes=previous.clippingPlanes;
      target.transparent=previous.transparent;target.opacity=previous.opacity;
      target.depthWrite=previous.depthWrite;target.needsUpdate=true;
      tubes.material=target;
    }
    riskEnabled = enabled;
    riskValues = values && typeof values === 'object' ? values : {};
    let count = 0;
    knownMembers.forEach((member,i)=>{
      const value = riskValues[String(member[0])];
      const valid = typeof value === 'number' && Number.isFinite(value) && value >= 0;
      const color = enabled && valid ? stressColor(value) : (enabled ? new THREE.Color('#929da8') : memberColor(member));
      if(valid)count++;
      tubes.setColorAt(i,color);
    });
    if(missingLines){
      const colors=[];
      for(const member of data.members){
        if(data.sections[member[4]].diameter_m)continue;
        const v=riskValues[String(member[0])];
        const c=enabled ? (typeof v==='number' && Number.isFinite(v) && v>=0 ? stressColor(v) : new THREE.Color('#929da8')) : new THREE.Color('#53738e');
        colors.push(c.r,c.g,c.b,c.r,c.g,c.b);
      }
      missingLines.geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
      missingLines.material.vertexColors=true;missingLines.material.color.set('#ffffff');missingLines.material.needsUpdate=true;
    }
    tubes.instanceColor.needsUpdate=true;
    root.dataset.risk=String(enabled); root.dataset.riskValueCount=String(count);
    root.dataset.stressPalette='continuous-endpoint-gradient';
    root.dataset.stressUnit='MPa';
    root.dataset.stressMax=String(data.stress?.range_mpa[1] ?? '');
    if(enabled && !count) notify('应力结果未接入。');
    requestRender();
  }
  function hideMember(id) {
    const index = knownMembers.findIndex(member=>member[0]===id);
    if(index<0){notify('该构件尚无实体截面，暂不支持实体隐藏。');return;}
    if(!hiddenMembers.has(index)) {
      const matrix = new THREE.Matrix4(); tubes.getMatrixAt(index,matrix); hiddenMembers.set(index,matrix);
    }
    tubes.setMatrixAt(index,new THREE.Matrix4().makeScale(0,0,0));
    tubes.instanceMatrix.needsUpdate=true;
    root.dataset.hiddenCount=String(hiddenMembers.size);
    renderer.shadowMap.needsUpdate=true;
    highlight(0); notify(`已隐藏单元 ${id}，点击“重置”可恢复。`);
  }
  function restoreMembers() {
    for(const [index,matrix] of hiddenMembers)tubes.setMatrixAt(index,matrix);
    hiddenMembers.clear();tubes.instanceMatrix.needsUpdate=true;
    root.dataset.hiddenCount='0'; renderer.shadowMap.needsUpdate=true;
  }
  let userMoved = false;
  let currentView = 'perspective';
  const views = { perspective: new THREE.Vector3(.35, 1.8, .5).normalize(),
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
    if(view==='perspective')controls.target.add(new THREE.Vector3(span*.16,span*.06,span*.05));
    camera.position.copy(controls.target).addScaledVector(direction, distance * (view==='perspective'?1.75:1.08));
    camera.lookAt(controls.target);
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
      root.dataset.camera = JSON.stringify(camera.position.toArray().map(v=>+v.toFixed(4)));
      site.update(camera, controls.target);
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
    const hit = raycaster.intersectObject(tubes, false).find(hit=>!hiddenMembers.has(hit.instanceId) && (!clipEnabled || clipPlane.distanceToPoint(hit.point)>=0));
    if(!hit)return null;
    const member=knownMembers[hit.instanceId];
    if(hiddenMembers.has(hit.instanceId))return null;
    if(clipEnabled && clipPlane.distanceToPoint(hit.point)<0)return null;
    return member;
  }
  renderer.domElement.addEventListener('pointerdown', event => { pressed = true; pointerStart = [event.clientX, event.clientY]; });
  window.addEventListener('pointerup', event => {
    const wasPressed = pressed;
    pressed = false;
    if (!wasPressed || event.button !== 0 || !pointerStart || Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) > 4) return;
    const member = pick(event);
    if(toolMode==='hide') {
      if(member)hideMember(member[0]);
      else notify('请点击可见的钢管构件进行隐藏。');
    } else if(toolMode==='select' || toolMode==='rotate') highlight(member ? member[0] : 0);
  });
  renderer.domElement.addEventListener('pointermove', event => {
    if (pressed || performance.now() - lastPick < 120) return;
    lastPick = performance.now();
    const member = pick(event);
    if (!member) { tooltip.style.display = 'none'; return; }
    const section = data.sections[member[4]];
    const length = positions.get(member[1]).distanceTo(positions.get(member[2]));
    const wall = section.wall_m ? `<br>壁厚：${(section.wall_m * 1000).toFixed(2).replace(/\.?0+$/, '')} mm` : '';
    const html = `<b>单元 ${member[0]}</b><br>截面：${safe(section.name)}<br>外径：${(section.diameter_m * 1000).toFixed(1)} mm${wall}<br>材料：${safe(data.materials[member[3]])}<br>长度：${length.toFixed(3)} m<br>${safe(stressText(member[0]))}<br>点击高亮杆件`;
    const rect = root.getBoundingClientRect();
    showTooltip(html, event.clientX - rect.left, event.clientY - rect.top);
  });
  renderer.domElement.addEventListener('pointerleave', () => { tooltip.style.display = 'none'; });
  for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => { userMoved = false; fitCamera(button.dataset.view); });
  function resetView() { restoreMembers();setClip(false);setTool('rotate');userMoved=false;fitCamera('perspective');highlight(0);parent.postMessage({type:'platform-reset'},'*'); }
  document.getElementById('reset').addEventListener('click',resetView);
  window.addEventListener('message',e=>{
    if(e.source!==parent || e.data?.type!=='platform-view')return;
    const command=e.data;
    if(command.action==='reset')resetView();
    else if(command.action==='top'){userMoved=false;fitCamera('top');}
    else if(command.action==='sensors')sensorLayer.style.display=command.value?'':'none';
    else if(command.action==='tool' && ['rotate','pan','zoom','select','hide'].includes(command.value)){setTool(command.value);if(command.value==='hide' && selectedID)hideMember(selectedID);}
    else if(command.action==='clip')setClip(!!command.value,command.axis,command.position);
    else if(command.action==='transparent')setTransparent(!!command.value);
    else if(command.action==='risk')setRisk(!!command.value,command.values ?? riskValues);
    else if(command.action==='select-id'){const id=Number(command.value);if(Number.isSafeInteger(id)&&memberByID.has(id)){highlight(id);notify(`已选择单元 ${id}。`);}else notify('模型中没有此单元编号。');}
    else if(command.action==='hide-selected'){if(selectedID)hideMember(selectedID);else notify('请先选中构件，或使用隐藏模式直接点击构件。');}
  });
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
  setTool('rotate');root.dataset.hiddenCount='0';root.dataset.clipping='false';root.dataset.risk='false';root.dataset.transparent='false';
  requestRender();
}
init().catch(error => {
  loading.textContent = '实体模型加载失败，请切换侧栏中的“线框模型”继续查看。';
  root.dataset.error = error.message;
  console.error('Steel viewer:', error);
});
