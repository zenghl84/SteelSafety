// A local, Z-up landscape fitted to the MGT footprint. No remote assets.
export function createSiteEnvironment(THREE, { bounds, centre, size, span, floorZ }) {
  const group = new THREE.Group();
  group.name = 'natural-industrial-campus';
  const halfX = size.x * .5 + span * .035;
  const halfY = size.y * .5 + span * .035;
  const margin = span * .09;
  let seed = 1505;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  function outsideDistance(x, y) {
    return Math.hypot(Math.max(Math.abs(x - centre.x) - halfX, 0),
      Math.max(Math.abs(y - centre.y) - halfY, 0));
  }
  function terrainHeight(x, y) {
    const u = (x - centre.x) / span, v = (y - centre.y) / span;
    const blend = THREE.MathUtils.smoothstep(outsideDistance(x, y), margin, span * .8);
    const dunes = .007 * Math.sin(u * 3.7 + v * 1.8)
      + .004 * Math.sin(v * 6.3 - u * 1.4) + .003 * Math.cos(u * 8.1 + v * 4.5);
    return floorZ - .08 + blend * span * (dunes + .006);
  }

  const skyCanvas=document.createElement('canvas');skyCanvas.width=2048;skyCanvas.height=1024;
  const skyCtx=skyCanvas.getContext('2d'),gradient=skyCtx.createLinearGradient(0,0,0,1024);
  gradient.addColorStop(0,'#408cd0');gradient.addColorStop(.45,'#9ac8e7');gradient.addColorStop(.58,'#e2edf0');gradient.addColorStop(1,'#c8d4ca');skyCtx.fillStyle=gradient;skyCtx.fillRect(0,0,2048,1024);
  for(let i=0;i<95;i++) {
    const x=random()*2048,y=250+random()*210,rx=22+random()*80,ry=7+random()*15;
    skyCtx.save();skyCtx.translate(x,y);skyCtx.scale(rx,ry);const g=skyCtx.createRadialGradient(0,0,0,0,0,1);g.addColorStop(0,'rgba(255,255,255,.45)');g.addColorStop(1,'rgba(255,255,255,0)');skyCtx.fillStyle=g;skyCtx.fillRect(-1,-1,2,2);skyCtx.restore();
  }
  const skyTexture=new THREE.CanvasTexture(skyCanvas);skyTexture.colorSpace=THREE.SRGBColorSpace;
  const sky=new THREE.Mesh(new THREE.SphereGeometry(span*14,64,32),new THREE.MeshBasicMaterial({map:skyTexture,side:THREE.BackSide,depthWrite:false,fog:false,toneMapped:false}));
  sky.rotation.x=Math.PI/2;sky.position.copy(centre);sky.renderOrder=-3;group.add(sky);

  // Flat, landscaped campus with a paved inspection apron and perimeter roads.
  // Deterministic, locally generated surface textures retain detail during orbiting.
  function surfaceTexture(base,kind) {
    const c=document.createElement('canvas');c.width=c.height=512;const ctx=c.getContext('2d');
    ctx.fillStyle=base;ctx.fillRect(0,0,512,512);
    for(let i=0;i<24000;i++) {
      const x=random()*512,y=random()*512,v=Math.floor(85+random()*100);
      ctx.fillStyle=`rgba(${v},${v},${v},${kind==='grass'?.14:.09})`;
      ctx.fillRect(x,y,kind==='grass'?2:1,kind==='grass'?4:1);
    }
    if(kind==='grass')for(let i=0;i<160;i++) {
      const x=random()*512,y=random()*512,r=12+random()*65;
      const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,i%2?'#7f895c55':'#365d3e55');g.addColorStop(1,'#56734a00');ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);
    }
    const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(kind==='grass'?25:12,kind==='grass'?25:12);t.anisotropy=4;return t;
  }
  const surfaces={grass:surfaceTexture('#718264','grass'),concrete:surfaceTexture('#b7bbb7','concrete'),road:surfaceTexture('#586064','road')};
  const material = (color, roughness=.9) => new THREE.MeshStandardMaterial({color, roughness});
  function slab(w,h,x,y,z,color) {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w,h), material(color));
    mesh.position.set(centre.x+x,centre.y+y,floorZ+z); mesh.receiveShadow=true;
    group.add(mesh); return mesh;
  }
  const meadow=slab(span*28,span*28,0,0,-.1,'#ffffff');meadow.material.map=surfaces.grass;
  const apronX=halfX+span*.08, apronY=halfY+span*.08;
  const road=slab(apronX*2+span*.18,apronY*2+span*.18,0,0,.005,'#ffffff');road.material.map=surfaces.road;
  const concrete=slab(apronX*2,apronY*2,0,0,.02,'#ffffff');concrete.material.map=surfaces.concrete;
  const seams=[]; const pitch=span*.07;
  for(let x=-apronX;x<=apronX;x+=pitch)seams.push(centre.x+x,centre.y-apronY,floorZ+.025,centre.x+x,centre.y+apronY,floorZ+.025);
  for(let y=-apronY;y<=apronY;y+=pitch)seams.push(centre.x-apronX,centre.y+y,floorZ+.025,centre.x+apronX,centre.y+y,floorZ+.025);
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(seams,3));
  group.add(new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:'#9eafb9',transparent:true,opacity:.22})));
  // White curb edges and regularly spaced lane markings.
  for(const side of [-1,1]) {
    slab(span*.009,apronY*2,side*(apronX+span*.007),0,.03,'#f1f5f4');
    slab(apronX*2,span*.009,0,side*(apronY+span*.007),.03,'#f1f5f4');
    for(let x=-apronX;x<apronX;x+=span*.08)slab(span*.035,span*.003,x,side*(apronY+span*.048),.032,'#ecede4');
    for(let y=-apronY;y<apronY;y+=span*.08)slab(span*.003,span*.035,side*(apronX+span*.048),y,.032,'#ecede4');
  }
  // Two continuous, irregular mountain ranges, several model spans away.
  const mountainMaterials = [];
  function mountainRange(radius, height, color, phase) {
    const segments = 240, rows = 5;
    const vertices = [], colors = [], indices = [];
    const tint = new THREE.Color(color);
    const profile = [0, .44, 1, .53, 0];
    for (let row = 0; row < rows; row++) for (let i = 0; i <= segments; i++) {
      const angle = i / segments * Math.PI * 2;
      const ridge = .63 + .17 * Math.sin(angle * 7 + phase)
        + .12 * Math.sin(angle * 13 - phase * .7) + .08 * Math.cos(angle * 23 + phase);
      const radial = radius + span * (.12 * Math.sin(angle * 9 + phase) + row * .24);
      vertices.push(centre.x + Math.cos(angle) * radial, centre.y + Math.sin(angle) * radial,
        floorZ + height * ridge * profile[row]);
      const shade = .94 + .08 * Math.sin(angle * 13 + row * 1.9 + phase);
      colors.push(tint.r * shade, tint.g * shade, tint.b * shade);
      if (row < rows - 1 && i < segments) {
        const a = row * (segments + 1) + i, b = a + segments + 1;
        indices.push(a, a + 1, b, a + 1, b + 1, b);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1,
      transparent: true, opacity: .85, depthWrite: false, side: THREE.DoubleSide });
    material.onBeforeCompile = shader => {
      shader.uniforms.siteCentre = { value: new THREE.Vector2(centre.x, centre.y) };
      shader.vertexShader = 'varying vec2 mountainPosition;\n' + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\nmountainPosition = (modelMatrix * vec4(transformed, 1.0)).xy;');
      shader.fragmentShader = 'uniform vec2 siteCentre; varying vec2 mountainPosition;\n' + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>',
        `#include <color_fragment>
         vec2 viewerSide = cameraPosition.xy - siteCentre;
         float side = dot(normalize(mountainPosition - siteCentre),
           viewerSide / max(length(viewerSide), .001));
         diffuseColor.a *= 1.0 - smoothstep(-.2, .35, side);
         if (diffuseColor.a < .005) discard;`);
    };
    mountainMaterials.push(material);
    group.add(new THREE.Mesh(geometry, material));
  }
  mountainRange(span * 4.9, span * .56, '#91b2c9', 2.4);
  mountainRange(span * 3.25, span * .37, '#789e9c', .7);

  // Planned planting beds; the model footprint and foreground remain clear.
  let treeCount=0;
  const trunkMaterial=material('#746553');
  const crownMaterials=['#397c65','#4c8d69','#619c70'].map(c=>material(c));
  const trunkGeo=new THREE.CylinderGeometry(span*.0018,span*.0025,span*.026,7);trunkGeo.rotateX(Math.PI/2);
  const crownGeo=new THREE.IcosahedronGeometry(1,2);
  function tree(x,y,scale=1) {
    const z=floorZ+.035,h=span*.026*scale;
    const trunk=new THREE.Mesh(trunkGeo,trunkMaterial);trunk.position.set(centre.x+x,centre.y+y,z+h*.5);trunk.scale.setScalar(scale);group.add(trunk);
    for(let i=0;i<16;i++) {
      const crown=new THREE.Mesh(crownGeo,crownMaterials[(treeCount+i)%3]);
      const a=random()*Math.PI*2,r=span*.012*Math.sqrt(random())*scale;
      crown.position.set(centre.x+x+Math.cos(a)*r,centre.y+y+Math.sin(a)*r,z+h+span*(.002+random()*.019)*scale);
      crown.scale.set(span*(.004+random()*.004)*scale,span*(.004+random()*.004)*scale,span*(.005+random()*.006)*scale);crown.castShadow=true;group.add(crown);
    }
    treeCount++;
  }
  for(const side of [-1,1]) {
    const x=side*(apronX+span*.15);
    slab(span*.078,apronY*2+span*.2,x,0,.016,'#c7d3cd');
    slab(span*.065,apronY*2+span*.18,x,0,.026,'#6f9d77');
    for(let y=-apronY-span*.04;y<=apronY+span*.04;y+=span*.095)tree(x+(random()-.5)*span*.018,y+(random()-.5)*span*.024,.8+random()*.6);
    const y=side*(apronY+span*.15);
    // Break the front planting into two wings to keep a central inspection approach.
    for(const wing of [-1,1]) {
      const bx=wing*apronX*.72;
      slab(apronX*.5,span*.065,bx,y,.018,'#c7d3cd');
      slab(apronX*.5-span*.012,span*.052,bx,y,.028,'#6f9d77');
      for(let x=bx-apronX*.21;x<=bx+apronX*.21;x+=span*.09)tree(x+(random()-.5)*span*.014,y+(random()-.5)*span*.014,.65+random()*.4);
    }
  }

  // Two contextual cooling towers sit outside the measured model footprint.
  function coolingTower(x,y,height,radius) {
    const points=[];
    for(let i=0;i<=48;i++) {
      const t=i/48;
      const r=radius*(.59+.41*Math.pow((t-.66)/.66,2));
      points.push(new THREE.Vector2(r,height*t));
    }
    const shellMaterial=new THREE.MeshStandardMaterial({color:'#b9b6aa',roughness:.92,side:THREE.DoubleSide,map:surfaces.concrete});
    const shell=new THREE.Mesh(new THREE.LatheGeometry(points,80),shellMaterial);
    shell.rotation.x=Math.PI/2;shell.position.set(centre.x+x,centre.y+y,floorZ+height*.07);shell.castShadow=true;shell.receiveShadow=true;group.add(shell);
    const rim=new THREE.Mesh(new THREE.TorusGeometry(points.at(-1).x,height*.005,8,80),material('#a6a497'));
    rim.position.set(centre.x+x,centre.y+y,floorZ+height*1.07);group.add(rim);
    for(let i=0;i<28;i++) {
      const a=i/28*Math.PI*2;
      const leg=new THREE.Mesh(new THREE.CylinderGeometry(radius*.016,radius*.024,height*.10,5),material('#96998e'));
      leg.rotation.x=Math.PI/2;leg.position.set(centre.x+x+Math.cos(a)*radius*.96,centre.y+y+Math.sin(a)*radius*.96,floorZ+height*.05);group.add(leg);
    }
  }
  coolingTower(halfX+span*.34,-span*.08,span*.43,span*.15);
  coolingTower(halfX+span*.05,-span*.43,span*.36,span*.125);
  // A shallow landscape basin echoes the project portrait without covering the inspection apron.
  const waterY=apronY+span*.34;
  slab(size.x+span*.8,span*.35,0,waterY,.015,'#c2c7b4');
  const water=slab(size.x+span*.775,span*.325,0,waterY,.025,'#517f90');
  water.material.roughness=.2;water.material.metalness=.42;water.material.envMapIntensity=1.1;
  water.material.onBeforeCompile=shader=>{
    shader.vertexShader='varying vec2 waterPosition;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nwaterPosition=position.xy;');
    shader.fragmentShader='varying vec2 waterPosition;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>','#include <normal_fragment_maps>\nnormal=normalize(normal+vec3(.035*sin(waterPosition.x*1.8+waterPosition.y*.8),.018*sin(waterPosition.y*2.8),0.0));');
  };
  group.userData={kind:'natural-industrial-campus',vegetationCount:treeCount,
    clearBounds:[bounds.min.x-margin,bounds.max.x+margin,bounds.min.y-margin,bounds.max.y+margin]};
  return {
    group,
    update(camera, target) {
      // Fade distant scenery in a plan view, preserving a clear inspection view.
      const distance = camera.position.distanceTo(target);
      const elevation = (camera.position.z - target.z) / Math.max(distance, .001);
      const opacity = 1 - THREE.MathUtils.smoothstep(elevation, .8, .97);
      for (const material of mountainMaterials) material.opacity = .85 * opacity;
    }
  };
}
