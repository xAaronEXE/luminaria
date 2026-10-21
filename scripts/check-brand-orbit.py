"""Verify concentric counter-rotation using a conservative geometric bound."""
import io,json,math
from pathlib import Path
import resvg_py
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
image=Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_path=str(ROOT/'web/brand/luminaria.svg'),width=800))).convert('RGBA')
weights=list(image.getchannel('A').getdata())
total=sum(weights)
center=[sum((i%800)*v for i,v in enumerate(weights))/total,sum((i//800)*v for i,v in enumerate(weights))/total]
radius=max(math.hypot(i%800-400,i//800-400)+math.sqrt(2) for i,v in enumerate(weights) if v)
scale=.36
# Every projected torus centerline point is at least R*cos(tilt) from
# the origin. A projected tube offset is at most r. Their difference is
# a conservative empty disk, valid at every angle and counter-rotation phase.
aperture=238*math.cos(.28)-76
clearance=aperture-radius*scale
assert all(abs(x-400)<.2 for x in center),center
assert clearance>20,clearance
samples=[]
for degree in range(1440):
    theta=math.radians(degree/4)
    # Relative orientation advances at twice the angle for equal/opposite motion.
    x,y=radius*scale*math.cos(2*theta),radius*scale*math.sin(2*theta)
    samples.append(aperture-math.hypot(x,y))
assert min(samples)>20
report={'canvas':800,'optical_center':center,'uniform_logo_scale':scale,'logo_bounding_radius':radius,'conservative_aperture_radius':aperture,'minimum_clearance_svg_units':clearance,'quarter_degree_samples':1440,'full_rotation_clear':True,'reason':'Conservative empty-disk bound covers every continuous relative orientation, not only samples.','rotation_seconds':48,'opposite_directions':True}
(ROOT/'docs/brand-orbit-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
