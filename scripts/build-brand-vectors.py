"""Build original, resolution-independent Luminaria artwork. No embedded bitmap."""
import math,re,sys,io
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

OUT = Path(__file__).resolve().parents[1] / 'web' / 'brand'
TAU = math.tau

def project(x, y, z):
    a = -1.02
    return (400 + x, 385 + y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))

def torus(u, v):
    r = 238 + 76 * math.cos(v)
    return project(r * math.cos(u), r * math.sin(u), 76 * math.sin(v))

def path(points):
    return 'M' + ' L'.join(f'{p[0]:.2f},{p[1]:.2f}' for p in points)

def lettering(text,x,y,size,color):
    font=TTFont('C:/Windows/Fonts/segoeui.ttf')
    glyphs=font.getGlyphSet();cmap=font.getBestCmap();scale=size/font['head'].unitsPerEm
    cursor=0;parts=[]
    for char in text:
        glyph=glyphs[cmap[ord(char)]];pen=SVGPathPen(glyphs);glyph.draw(pen)
        parts.append(f'<path transform="translate({cursor} 0)" d="{pen.getCommands()}"/>')
        cursor+=glyph.width
    return f'<g fill="{color}" transform="translate({x} {y}) scale({scale} {-scale})">{"".join(parts)}</g>'

def lattice():
    lines = []
    for i in range(48):
        u = TAU * i / 48
        points = [torus(u, TAU*j/72) for j in range(73)]
        lines.append(f'<path d="{path(points)}"/>')
    for j in range(18):
        v = TAU*j/18
        points = [torus(TAU*i/160, v) for i in range(161)]
        lines.append(f'<path d="{path(points)}"/>')
    nodes=[]
    for i in range(48):
        for j in range(0,18,3):
            x,y,z=torus(TAU*i/48,TAU*j/18)
            nodes.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{1.1 if z<0 else 1.65}" opacity="{.3 if z<0 else .85}"/>')
    trails=[]
    for k in range(3):
        pts=[torus(TAU*i/160,TAU*(k+.4)/3) for i in range(161)]
        trails.append(f'<path class="light-packet packet-{k}" pathLength="1000" d="{path(pts)}" stroke="url(#silver)" stroke-width="1.8" opacity=".9"/>')
    return f'<g class="lattice-lines" fill="none" stroke="#b9b5a7" stroke-width=".65" opacity=".34">{"".join(lines)}</g><g class="lattice-nodes" fill="#eee5d1">{"".join(nodes)}</g><g fill="none">{"".join(trails)}</g>'

def ribbon():
    # Hand-shaped continuous ribbon surfaces, following the original rounded
    # triangular brand silhouette rather than substituting a mathematical knot.
    content = '''<defs>
    <linearGradient id="studio-light" x1="0" y1=".15" x2="1" y2=".85"><stop stop-color="#fff5d9" stop-opacity=".22"/><stop offset=".24" stop-color="#151a16" stop-opacity=".12"/><stop offset=".48" stop-color="#fff9ea" stop-opacity=".04"/><stop offset=".72" stop-color="#181c17" stop-opacity=".18"/><stop offset="1" stop-color="#fff0cc" stop-opacity=".28"/></linearGradient>
    <linearGradient id="crown" x1=".1" y1=".7" x2=".9" y2=".2"><stop stop-color="#746d5e"/><stop offset=".24" stop-color="#d2c6a8"/><stop offset=".52" stop-color="#fff7e4"/><stop offset=".8" stop-color="#dfd3b7"/><stop offset="1" stop-color="#aea58e"/></linearGradient>
    <linearGradient id="rise" x1=".1" y1=".8" x2=".85" y2=".15"><stop stop-color="#a69c84"/><stop offset=".25" stop-color="#efe5cb"/><stop offset=".55" stop-color="#fff8e8"/><stop offset=".84" stop-color="#d4c8ad"/><stop offset="1" stop-color="#8c8370"/></linearGradient>
    <linearGradient id="base" x1=".2" y1="0" x2=".7" y2="1"><stop stop-color="#fff9e9"/><stop offset=".3" stop-color="#e7dcc2"/><stop offset=".68" stop-color="#c4b89c"/><stop offset="1" stop-color="#f6edd8"/></linearGradient>
    <linearGradient id="inside" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#151b17"/><stop offset=".5" stop-color="#666356"/><stop offset="1" stop-color="#151a16"/></linearGradient>
    <radialGradient id="ground"><stop stop-color="#e8d9b0" stop-opacity=".15"/><stop offset="1" stop-color="#e8d9b0" stop-opacity="0"/></radialGradient>
    <mask id="opening" maskUnits="userSpaceOnUse" x="0" y="0" width="800" height="800"><rect width="800" height="800" fill="white"/><path d="M402 304 C410 299 424 326 440 360 C465 411 490 446 521 470 C550 495 521 523 484 522 L336 510 C307 508 301 491 319 464 C357 413 377 362 388 322 C391 311 395 306 402 304 Z" fill="black"/></mask>
    </defs>
    <ellipse cx="405" cy="687" rx="230" ry="30" fill="url(#ground)"/>
    <g mask="url(#opening)">
    <path d="M285 237 C291 161 340 117 396 132 C467 154 511 246 537 335 L640 526 C665 593 599 638 504 626 L259 612 C172 602 171 532 213 454 Z" fill="url(#inside)"/>
    <path d="M283 250 C270 182 300 119 360 105 C439 85 491 148 531 233 C582 343 599 435 652 506 C608 494 563 465 534 432 C479 367 456 246 410 205 C359 160 306 188 283 250 Z" fill="url(#crown)"/>
    <path d="M410 205 C357 211 346 286 302 343 C262 395 188 430 160 499 C117 604 164 661 246 651 C210 629 215 591 253 550 C303 497 360 457 389 397 C418 338 399 256 410 205 Z" fill="url(#rise)"/>
    <path d="M160 499 C138 562 182 586 264 590 C371 596 467 609 550 580 C629 552 657 518 624 461 C682 496 708 579 664 626 C609 688 467 677 362 671 C255 667 145 682 139 594 C137 561 144 527 160 499 Z" fill="url(#base)"/>
    <path d="M410 205 C397 265 417 333 389 397 C368 444 318 486 285 517 C352 483 430 532 500 553 C557 570 609 548 652 506 C597 499 547 462 511 412 C470 355 460 254 410 205 Z" fill="url(#inside)" opacity=".87"/>
    <path d="M283 250 C299 194 354 158 410 205 C456 246 479 367 534 432 C563 465 608 494 652 506" fill="none" stroke="#fff8e6" stroke-opacity=".65" stroke-width="1.4"/>
    <path d="M160 499 C138 562 182 586 264 590 C371 596 467 609 550 580 C594 565 629 542 641 521" fill="none" stroke="#fff9e8" stroke-opacity=".8" stroke-width="1.3"/>
    <path d="M410 205 C357 211 346 286 302 343 C262 395 188 430 160 499" fill="none" stroke="#fff9e9" stroke-opacity=".55" stroke-width="1.2"/>
    </g>
    '''
    def reflect(match):
        face=match.group(0)
        sheen=re.sub(r'fill="url\(#[^)]+\)"','fill="url(#studio-light)"',face)
        return face+sheen
    return re.sub(r'<path d="[^"]+" fill="url\(#(?:crown|rise|base|inside)\)"[^>]*/>',reflect,content)

def network():
    lines=[]
    for i in range(9):
        y=80+i*88
        lines.append(f'<path d="M-100 {y} C350 {y-220} 550 {y+260} 950 {y+100} S1450 {y-180} 1750 {y+20}"/>')
    return '<g fill="none" stroke="#d0c4a7" stroke-width="1" opacity=".09">'+''.join(lines)+'</g><g fill="#dfd2b2" opacity=".4"><circle cx="180" cy="150" r="3"/><circle cx="730" cy="610" r="2.5"/><circle cx="1350" cy="208" r="3"/><circle cx="1120" cy="680" r="2"/></g>'

DEFS='<defs><linearGradient id="silver" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f5f1e6"/><stop offset=".45" stop-color="#999e9b"/><stop offset="1" stop-color="#eee8d8"/></linearGradient><radialGradient id="halo"><stop stop-color="#b2b9b1" stop-opacity=".09"/><stop offset="1" stop-color="#b2b9b1" stop-opacity="0"/></radialGradient></defs>'

MOTION='''<style>
.lattice-lines{animation:light-breath 9s ease-in-out infinite}.lattice-nodes{animation:node-breath 7s ease-in-out infinite}.light-packet{stroke-dasharray:42 22 5 931;animation:packet-flow 12s linear infinite}.packet-1{animation-duration:17s;animation-delay:-6s}.packet-2{animation-duration:21s;animation-delay:-13s}
@keyframes light-breath{0%,100%{opacity:.26}50%{opacity:.62}}@keyframes node-breath{0%,100%{opacity:.45}50%{opacity:1}}@keyframes packet-flow{from{stroke-dashoffset:0}to{stroke-dashoffset:-1000}}
@media(prefers-reduced-motion:reduce){.lattice-lines,.lattice-nodes,.light-packet{animation:none}.light-packet{stroke-dasharray:none;opacity:.4}}
</style>'''

for name, content in [('toroidal',lattice()),('ribbon',ribbon())]:
    title='Toroidal lattice' if name=='toroidal' else 'Interwoven ivory ribbon'
    # Ground lighting stays fixed in the HTML scene while the symbol rotates.
    rotating_content=content.replace('<ellipse cx="405" cy="687" rx="230" ry="30" fill="url(#ground)"/>','')
    if name=='ribbon':
        # Alpha-weighted optical center measured at 406.81,442.48 on the
        # 800-square master. Center the visible mass, not its empty canvas.
        rotating_content=f'<g transform="translate(-6.81 -42.48)">{rotating_content}</g>'
    art=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img" aria-labelledby="title"><title id="title">Luminaria — {title}</title>{DEFS}{MOTION}{rotating_content}</svg>'
    (OUT/f'sign-in-{name}.svg').write_text(art,encoding='utf-8')
    words=lettering('Luminaria',100,355,100,'#f4ecdc')+lettering('Intelligence, on your terms.',105,425,34,'#b8b9ad')+lettering('Local models. Real tools. Your control.',106,485,23,'#9b9f93')
    banner=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800" role="img" aria-labelledby="title"><title id="title">Luminaria — Intelligence, on your terms.</title>{DEFS}<rect width="1600" height="800" fill="#121815"/>{network()}<g transform="translate(800 0)">{content}</g>{words}</svg>'
    (OUT/f'social-cover-{name}.svg').write_text(banner,encoding='utf-8')
    if name=='ribbon':
        (OUT/'luminaria.svg').write_text(art,encoding='utf-8')
        (OUT/'social-cover.svg').write_text(banner,encoding='utf-8')
# A near-frontal lattice gives the nested symbol a clear, stable aperture.
original_project=project
def project(x,y,z):
    a=-.28
    return (400+x,400+y*math.cos(a)-z*math.sin(a),y*math.sin(a)+z*math.cos(a))
ambient=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img" aria-label="Counter-rotating toroidal lattice">{DEFS}{MOTION}{lattice()}</svg>'
(OUT/'sign-in-orbit.svg').write_text(ambient,encoding='utf-8')
header=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800" role="img" aria-labelledby="title"><title id="title">Luminaria — Intelligence, on your terms.</title>{DEFS}<rect width="1600" height="800" fill="#121815"/>{network()}<g transform="translate(800 0)">{lattice()}<g transform="translate(400 400) scale(.36) translate(-400 -400)">{rotating_content}</g></g>{words}</svg>'
for name in ('social-cover.svg','social-cover-ribbon.svg'):
    (OUT/name).write_text("\n".join(line.rstrip() for line in header.splitlines()),encoding='utf-8')
project=original_project
print('Created vector branding and nested-orbit artwork.')

if '--export' in sys.argv:
    import resvg_py
    from PIL import Image
    mark=resvg_py.svg_to_bytes(svg_path=str(OUT/'luminaria.svg'),width=1024)
    (OUT/'luminaria.png').write_bytes(mark)
    Image.open(io.BytesIO(mark)).save(OUT/'luminaria.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    cover=resvg_py.svg_to_bytes(svg_path=str(OUT/'social-cover.svg'),width=1730)
    (OUT/'social-cover.png').write_bytes(cover)
    Image.open(io.BytesIO(cover)).convert('RGB').save(OUT/'social-cover.jpg',quality=95)
    print('Exported app PNG, desktop ICO and social PNG/JPEG from SVG masters.')
